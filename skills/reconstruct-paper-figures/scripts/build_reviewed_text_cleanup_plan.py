from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import statistics
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from PIL import Image, ImageChops, ImageDraw, ImageFilter


MANIFEST_SCHEMA = "text-detection-manifest-v1"
REVIEW_SCHEMA = "text-cleanup-review-v1"
PLAN_SCHEMA = "safe-text-cleanup-v1"
ALLOWED_ACTIONS = {"cleanup_replace", "preserve"}
ALLOWED_METHODS = {"solid_fill", "border_median", "horizontal_linear", "vertical_linear"}
LOSSLESS_SUFFIXES = {".png", ".tif", ".tiff", ".bmp"}


def fail(message: str) -> None:
    raise ValueError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_inside_workspace(
    value: Any,
    base: Path,
    workspace: Path,
    must_exist: bool = True,
) -> Path:
    if not isinstance(value, (str, os.PathLike)) or not str(value).strip():
        fail("A non-empty path is required")
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = base / candidate
    candidate = candidate.resolve()
    workspace = workspace.resolve()
    try:
        candidate.relative_to(workspace)
    except ValueError:
        fail("Path must remain inside workspace: %s" % candidate)
    if must_exist and not candidate.is_file():
        fail("Required file does not exist: %s" % candidate)
    return candidate


def require_hash(value: Any, name: str) -> str:
    text = str(value or "").lower()
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        fail("%s must be a lowercase SHA-256 hex digest" % name)
    return text


def finite_number(value: Any, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        fail("%s must be numeric" % name)
    if not math.isfinite(number):
        fail("%s must be finite" % name)
    return number


def parse_bbox(value: Any, name: str, size: Tuple[int, int]) -> Tuple[int, int, int, int]:
    if isinstance(value, dict):
        values = [value.get("x"), value.get("y"), value.get("width"), value.get("height")]
    else:
        values = value
    if not isinstance(values, list) or len(values) != 4:
        fail("%s must be [x, y, width, height]" % name)
    numbers = [finite_number(item, name) for item in values]
    if any(abs(item - round(item)) > 1e-6 for item in numbers):
        fail("%s entries must be integral pixels" % name)
    x, y, width, height = [int(round(item)) for item in numbers]
    if x < 0 or y < 0 or width <= 0 or height <= 0:
        fail("%s must have non-negative origin and positive size" % name)
    if x + width > size[0] or y + height > size[1]:
        fail("%s is outside source image" % name)
    return x, y, x + width, y + height


def parse_polygon(detection: dict, size: Tuple[int, int]) -> List[Tuple[float, float]]:
    polygon = detection.get("polygon_px")
    if not isinstance(polygon, list) or len(polygon) < 3:
        x0, y0, x1, y1 = parse_bbox(detection.get("bbox_px"), "detection bbox", size)
        return [(x0, y0), (x1 - 1, y0), (x1 - 1, y1 - 1), (x0, y1 - 1)]
    result: List[Tuple[float, float]] = []
    for point in polygon:
        if not isinstance(point, list) or len(point) != 2:
            fail("detection polygon points must be [x, y]")
        x = finite_number(point[0], "polygon x")
        y = finite_number(point[1], "polygon y")
        if x < 0 or y < 0 or x > size[0] - 1 or y > size[1] - 1:
            fail("detection polygon is outside source image")
        result.append((x, y))
    return result


def mask_bbox(mask: Image.Image) -> Tuple[int, int, int, int]:
    bbox = mask.getbbox()
    if bbox is None:
        fail("Generated cleanup mask is empty")
    return tuple(int(value) for value in bbox)


def masks_intersect(first: Image.Image, second: Image.Image) -> bool:
    return bool(ImageChops.multiply(first, second).getbbox())


def bbox_mask(size: Tuple[int, int], bbox: Tuple[int, int, int, int]) -> Image.Image:
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rectangle((bbox[0], bbox[1], bbox[2] - 1, bbox[3] - 1), fill=255)
    return mask


def build_glyph_mask(
    source: Image.Image,
    polygon: Sequence[Tuple[float, float]],
    decision: dict,
) -> Tuple[Image.Image, dict]:
    size = source.size
    polygon_mask = Image.new("L", size, 0)
    ImageDraw.Draw(polygon_mask).polygon(list(polygon), fill=255)
    mode = str(decision.get("mask_mode", ""))
    if mode == "full_polygon":
        if decision.get("allow_full_polygon") is not True:
            fail("full_polygon requires allow_full_polygon=true after explicit flat-plate review")
        reason = str(decision.get("full_polygon_reason", "")).strip()
        if not reason:
            fail("full_polygon_reason is required")
        return polygon_mask, {"mode": mode, "reason": reason, "selected_fraction": 1.0}
    if mode != "foreground_delta":
        fail("mask_mode must be foreground_delta or explicitly approved full_polygon")

    threshold = finite_number(decision.get("foreground_delta", 24.0), "foreground_delta")
    if threshold <= 0 or threshold > 255:
        fail("foreground_delta must be in (0, 255]")
    ring_px = decision.get("ring_px", 3)
    if not isinstance(ring_px, int) or isinstance(ring_px, bool) or ring_px < 1 or ring_px > 64:
        fail("ring_px must be an integer from 1 to 64")
    maximum_fraction = finite_number(
        decision.get("max_foreground_fraction", 0.85), "max_foreground_fraction"
    )
    if maximum_fraction <= 0 or maximum_fraction >= 1:
        fail("max_foreground_fraction must be in (0, 1)")

    polygon_bbox = mask_bbox(polygon_mask)
    outer_bbox = (
        max(0, polygon_bbox[0] - ring_px),
        max(0, polygon_bbox[1] - ring_px),
        min(size[0], polygon_bbox[2] + ring_px),
        min(size[1], polygon_bbox[3] + ring_px),
    )
    source_rgb = source.convert("RGB")
    source_pixels = source_rgb.load()
    polygon_pixels = polygon_mask.load()
    samples: List[Tuple[int, int, int]] = []
    for y in range(outer_bbox[1], outer_bbox[3]):
        for x in range(outer_bbox[0], outer_bbox[2]):
            if polygon_pixels[x, y] == 0:
                samples.append(source_pixels[x, y])
    if not samples:
        fail("foreground_delta has no external ring samples")
    background = tuple(int(round(statistics.median(sample[channel] for sample in samples))) for channel in range(3))
    glyph = Image.new("L", size, 0)
    glyph_pixels = glyph.load()
    polygon_count = 0
    selected_count = 0
    for y in range(polygon_bbox[1], polygon_bbox[3]):
        for x in range(polygon_bbox[0], polygon_bbox[2]):
            if polygon_pixels[x, y] == 0:
                continue
            polygon_count += 1
            pixel = source_pixels[x, y]
            if max(abs(pixel[channel] - background[channel]) for channel in range(3)) >= threshold:
                glyph_pixels[x, y] = 255
                selected_count += 1
    if selected_count == 0:
        fail("foreground_delta selected no glyph pixels")
    selected_fraction = selected_count / float(polygon_count)
    if selected_fraction > maximum_fraction:
        fail("foreground_delta selected too much of the OCR polygon")
    return glyph, {
        "mode": mode,
        "foreground_delta": threshold,
        "ring_px": ring_px,
        "background_rgb": list(background),
        "polygon_pixels": polygon_count,
        "selected_pixels_before_expansion": selected_count,
        "selected_fraction": selected_fraction,
        "max_foreground_fraction": maximum_fraction,
    }


def atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(str(temporary), str(path))
    finally:
        if temporary.exists():
            temporary.unlink()


def png_bytes(image: Image.Image) -> bytes:
    descriptor, temporary_name = tempfile.mkstemp(suffix=".png")
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        image.save(str(temporary), format="PNG", optimize=False, compress_level=9)
        return temporary.read_bytes()
    finally:
        if temporary.exists():
            temporary.unlink()


def relative_path(target: Path, base: Path) -> str:
    return os.path.relpath(str(target), str(base)).replace("\\", "/")


def validate_replacement(replacement: Any, detection: dict, region_id: str) -> dict:
    if not isinstance(replacement, dict):
        fail("cleanup_replace decision requires replacement object")
    identifier = str(replacement.get("id", "")).strip()
    text = str(replacement.get("text", "")).strip()
    if not identifier or not text:
        fail("replacement id and text are required")
    family = str(replacement.get("font_family", "")).strip()
    if family != "Times New Roman":
        fail("replacement font_family must be Times New Roman")
    size = finite_number(replacement.get("font_size_pt"), "replacement.font_size_pt")
    if not math.isclose(size, 8.5, abs_tol=1e-9):
        fail("replacement font_size_pt must be exactly 8.5")
    x = finite_number(replacement.get("x_px"), "replacement.x_px")
    y = finite_number(replacement.get("y_px"), "replacement.y_px")
    result = dict(replacement)
    result.update({
        "id": identifier,
        "region_id": region_id,
        "text": text,
        "original_text": str(replacement.get("original_text", detection.get("text", ""))),
        "x_px": x,
        "y_px": y,
        "font_family": family,
        "font_size_pt": size,
    })
    return result


def build_reviewed_plan(
    source_path: Path,
    manifest_path: Path,
    review_path: Path,
    output_plan_path: Path,
    workspace: Path,
    force: bool = False,
) -> Dict[str, Any]:
    workspace = workspace.resolve()
    source_path = resolve_inside_workspace(source_path, Path.cwd(), workspace)
    manifest_path = resolve_inside_workspace(manifest_path, Path.cwd(), workspace)
    review_path = resolve_inside_workspace(review_path, Path.cwd(), workspace)
    output_plan_path = resolve_inside_workspace(output_plan_path, Path.cwd(), workspace, must_exist=False)
    if len({source_path, manifest_path, review_path, output_plan_path}) != 4:
        fail("Source, manifest, review, and output plan must be distinct files")
    if source_path.suffix.lower() not in LOSSLESS_SUFFIXES:
        fail("source image must be lossless PNG/TIFF/BMP")
    if output_plan_path.suffix.lower() != ".json":
        fail("output plan must be JSON")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    review = json.loads(review_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != MANIFEST_SCHEMA:
        fail("manifest schema_version must be %s" % MANIFEST_SCHEMA)
    if review.get("schema_version") != REVIEW_SCHEMA:
        fail("review schema_version must be %s" % REVIEW_SCHEMA)
    source_hash = sha256_file(source_path)
    manifest_source_hash = require_hash(manifest.get("source", {}).get("sha256"), "manifest source hash")
    if source_hash != manifest_source_hash:
        fail("manifest source hash does not match source image")
    if require_hash(review.get("source_sha256"), "review.source_sha256") != source_hash:
        fail("review source hash does not match source image")
    manifest_hash = sha256_file(manifest_path)
    if require_hash(review.get("detection_manifest_sha256"), "review.detection_manifest_sha256") != manifest_hash:
        fail("review detection manifest hash does not match")
    if manifest.get("read_only_import") is not True or manifest.get("ocr_runtime_invoked") is not False:
        fail("manifest must be a read-only OCR import")
    if manifest.get("cleanup_authorized") is not False:
        fail("OCR manifest must not authorize cleanup")
    if review.get("approval_status") != "approved":
        fail("review approval_status must be approved")
    if not str(review.get("approved_by", "")).strip() or not str(review.get("approval_note", "")).strip():
        fail("review approved_by and approval_note are required")
    if review.get("scientific_evidence") is not False:
        fail("review scientific_evidence must be explicitly false")
    if review.get("risk_class") != "non_evidence_flat_background":
        fail("review risk_class must be non_evidence_flat_background")

    with Image.open(str(source_path)) as opened:
        source = opened.convert("RGB")
        size = source.size
    if tuple(manifest.get("source", {}).get(key) for key in ("width_px", "height_px")) != size:
        fail("manifest source dimensions do not match source image")

    detections = manifest.get("detections")
    decisions = review.get("detections")
    if not isinstance(detections, list) or not detections:
        fail("manifest must contain detections")
    if not isinstance(decisions, list) or not decisions:
        fail("review must contain explicit detection decisions")
    detection_by_id = {str(item.get("id", "")): item for item in detections}
    if "" in detection_by_id or len(detection_by_id) != len(detections):
        fail("manifest detection ids must be unique and non-empty")
    decision_by_id = {str(item.get("detection_id", "")): item for item in decisions}
    if "" in decision_by_id or len(decision_by_id) != len(decisions):
        fail("review detection_id values must be unique and non-empty")
    if set(decision_by_id) != set(detection_by_id):
        fail("Every OCR detection must have exactly one explicit review decision")

    protected_raw = review.get("protected_regions", [])
    if not isinstance(protected_raw, list):
        fail("protected_regions must be a list")
    protected_masks = [
        bbox_mask(size, parse_bbox(item.get("bbox_px"), "protected region", size))
        for item in protected_raw
    ]

    mask_directory_value = str(review.get("mask_directory", "masks/reviewed-text-cleanup")).strip()
    mask_directory = resolve_inside_workspace(mask_directory_value, output_plan_path.parent, workspace, must_exist=False)
    maximum_fraction = finite_number(review.get("max_mask_area_fraction", 0.02), "max_mask_area_fraction")
    if maximum_fraction <= 0 or maximum_fraction > 1:
        fail("max_mask_area_fraction must be in (0, 1]")
    print_width_mm = finite_number(review.get("print_width_mm"), "print_width_mm")
    if print_width_mm <= 0 or print_width_mm > 1000:
        fail("print_width_mm must be in (0, 1000]")

    generated: List[Tuple[Path, Image.Image]] = []
    regions: List[dict] = []
    replacements: List[dict] = []
    preserve_ids: List[str] = []
    union = Image.new("L", size, 0)
    for detection_id in sorted(detection_by_id):
        detection = detection_by_id[detection_id]
        decision = decision_by_id[detection_id]
        action = str(decision.get("action", ""))
        if action not in ALLOWED_ACTIONS:
            fail("Unsupported review action for %s" % detection_id)
        if action == "preserve":
            preserve_ids.append(detection_id)
            continue
        if decision.get("approved") is not True:
            fail("cleanup_replace decision must be explicitly approved for %s" % detection_id)
        if decision.get("scientific_evidence") is not False:
            fail("cleanup_replace scientific_evidence must be false for %s" % detection_id)
        region_id = str(decision.get("region_id", "")).strip()
        if not region_id:
            fail("cleanup_replace region_id is required for %s" % detection_id)
        expand_px = decision.get("expand_px", 2)
        if not isinstance(expand_px, int) or isinstance(expand_px, bool) or expand_px < 0 or expand_px > 64:
            fail("expand_px must be an integer from 0 to 64")
        method = str(decision.get("method", ""))
        if method not in ALLOWED_METHODS:
            fail("Unsupported cleanup method for %s" % detection_id)
        parameters = decision.get("parameters", {})
        if not isinstance(parameters, dict):
            fail("cleanup parameters must be an object")
        if not str(decision.get("background_basis", "")).strip() or not str(decision.get("selection_rationale", "")).strip():
            fail("background_basis and selection_rationale are required for %s" % detection_id)

        mask, mask_generation = build_glyph_mask(
            source, parse_polygon(detection, size), decision
        )
        if expand_px:
            mask = mask.filter(ImageFilter.MaxFilter(expand_px * 2 + 1))
        for protected in protected_masks:
            if masks_intersect(mask, protected):
                fail("Generated mask intersects a protected region for %s" % detection_id)
        if masks_intersect(mask, union):
            fail("Generated cleanup masks overlap for %s" % detection_id)
        union = ImageChops.lighter(union, mask)
        bbox = mask_bbox(mask)
        mask_path = (mask_directory / (region_id + ".png")).resolve()
        try:
            mask_path.relative_to(mask_directory.resolve())
        except ValueError:
            fail("region_id creates an unsafe mask path")
        generated.append((mask_path, mask))
        regions.append({
            "id": region_id,
            "detection_id": detection_id,
            "bbox_px": [bbox[0], bbox[1], bbox[2] - bbox[0], bbox[3] - bbox[1]],
            "mask_file": relative_path(mask_path, output_plan_path.parent),
            "mask_sha256": hashlib.sha256(png_bytes(mask)).hexdigest(),
            "method": method,
            "parameters": parameters,
            "scientific_evidence": False,
            "background_basis": str(decision["background_basis"]),
            "selection_rationale": str(decision["selection_rationale"]),
            "mask_expansion_px": expand_px,
            "mask_generation": mask_generation,
            "ocr_text": str(detection.get("text", "")),
        })
        replacements.append(validate_replacement(decision.get("replacement"), detection, region_id))

    if not regions:
        fail("At least one detection must be approved for cleanup_replace")
    masked_fraction = union.histogram()[255] / float(size[0] * size[1])
    if masked_fraction > maximum_fraction:
        fail("Generated masks exceed max_mask_area_fraction")

    target_paths = [output_plan_path] + [path for path, _ in generated]
    if len(set(target_paths)) != len(target_paths):
        fail("Generated target paths must be unique")
    if any(path in {source_path, manifest_path, review_path} for path in target_paths):
        fail("Generated outputs must not overwrite evidence inputs")
    if not force:
        existing = [str(path) for path in target_paths if path.exists()]
        if existing:
            raise FileExistsError("Refusing to overwrite: %s" % ", ".join(existing))

    plan: Dict[str, Any] = {
        "schema_version": PLAN_SCHEMA,
        "sample_id": str(review.get("sample_id", "")).strip() or output_plan_path.stem,
        "source_image": relative_path(source_path, output_plan_path.parent),
        "source_sha256": source_hash,
        "output_image": str(review.get("output_image", "output/text-cleaned.png")),
        "combined_mask_output": str(review.get("combined_mask_output", "qa/text-cleanup-union-mask.png")),
        "audit_output": str(review.get("audit_output", "qa/text-cleanup.executor.audit.json")),
        "scientific_evidence": False,
        "risk_class": "non_evidence_flat_background",
        "approval_status": "approved",
        "approved_by": str(review["approved_by"]),
        "approval_note": str(review["approval_note"]),
        "max_mask_area_fraction": maximum_fraction,
        "print_width_mm": print_width_mm,
        "protected_regions": protected_raw,
        "regions": regions,
        "replacement_texts": replacements,
        "review_bridge": {
            "schema_version": "reviewed-text-cleanup-bridge-v1",
            "detection_manifest": relative_path(manifest_path, output_plan_path.parent),
            "detection_manifest_sha256": manifest_hash,
            "review_file": relative_path(review_path, output_plan_path.parent),
            "review_file_sha256": sha256_file(review_path),
            "all_detections_explicitly_decided": True,
            "cleanup_detection_ids": [item["detection_id"] for item in regions],
            "preserved_detection_ids": preserve_ids,
            "generated_mask_area_fraction": masked_fraction,
            "publication_ready": False,
            "manual_200_400_percent_review_required": True,
        },
    }

    for path, mask in generated:
        atomic_write(path, png_bytes(mask))
    atomic_write(output_plan_path, (json.dumps(plan, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return plan


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert a hash-bound OCR manifest plus explicit human decisions into guarded cleanup masks and a safe cleanup plan."
    )
    parser.add_argument("source_image", type=Path)
    parser.add_argument("detection_manifest", type=Path)
    parser.add_argument("review_file", type=Path)
    parser.add_argument("output_plan", type=Path)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--force", action="store_true")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    plan = build_reviewed_plan(
        args.source_image,
        args.detection_manifest,
        args.review_file,
        args.output_plan,
        args.workspace,
        force=args.force,
    )
    print(json.dumps({
        "output_plan": str(args.output_plan.resolve()),
        "cleanup_regions": len(plan["regions"]),
        "preserved_detections": len(plan["review_bridge"]["preserved_detection_ids"]),
        "publication_ready": False,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
