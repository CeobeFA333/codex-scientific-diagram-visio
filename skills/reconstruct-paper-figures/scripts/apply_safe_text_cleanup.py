#!/usr/bin/env python3
"""Apply narrowly scoped, non-generative text cleanup to lossless rasters.

The input plan binds every source and mask by SHA-256.  Cleanup is allowed only
for approved, explicitly non-scientific regions.  The executor changes pixels
inside binary masks and proves that decoded RGBA pixels outside the union mask
remain exactly unchanged.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
import statistics
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from PIL import Image


SCHEMA_VERSION = "safe-text-cleanup-v1"
LOSSLESS_SOURCE_SUFFIXES = {".png", ".tif", ".tiff", ".bmp"}
ALLOWED_METHODS = {
    "solid_fill",
    "border_median",
    "horizontal_linear",
    "vertical_linear",
}
SUPPORTED_8BIT_MODES = {"1", "L", "LA", "P", "RGB", "RGBA"}


def fail(message: str) -> None:
    raise ValueError(message)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def decoded_rgba_sha256(image: Image.Image) -> str:
    normalized = image.convert("RGBA")
    prefix = ("%dx%d:RGBA:" % normalized.size).encode("ascii")
    return sha256_bytes(prefix + normalized.tobytes())


def integer_values(value: Any, label: str) -> List[int]:
    if isinstance(value, (tuple, list)):
        values = list(value)
    else:
        values = [value]
    try:
        return [int(item) for item in values]
    except (TypeError, ValueError) as error:
        raise ValueError("Cannot verify %s" % label) from error


def validate_source_precision(opened: Image.Image, path: Path) -> None:
    image_format = str(opened.format or "").upper()
    if image_format == "TIFF":
        tags = getattr(opened, "tag_v2", None)
        if tags is None:
            fail("Cannot verify TIFF sample precision")
        bits_raw = tags.get(258)
        if bits_raw is None:
            fail("TIFF BitsPerSample is required")
        bits = integer_values(bits_raw, "TIFF BitsPerSample")
        if not bits or any(value not in {1, 2, 4, 8} for value in bits):
            fail("TIFF source uses unsupported sample precision: %s" % bits)
        sample_format_raw = tags.get(339, (1,))
        sample_formats = integer_values(sample_format_raw, "TIFF SampleFormat")
        if any(value != 1 for value in sample_formats):
            fail("TIFF source must use unsigned integer samples")
    elif image_format == "PNG":
        header = path.read_bytes()[:26]
        if len(header) < 26 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
            fail("Cannot verify PNG sample precision")
        bit_depth = header[24]
        if bit_depth not in {1, 2, 4, 8}:
            fail("PNG source uses unsupported sample precision: %d" % bit_depth)
    elif image_format == "BMP":
        header = path.read_bytes()[:30]
        if len(header) < 30 or header[:2] != b"BM":
            fail("Cannot verify BMP sample precision")
        bits_per_pixel = int.from_bytes(header[28:30], byteorder="little", signed=False)
        if bits_per_pixel not in {1, 4, 8, 24, 32}:
            fail("BMP source uses unsupported pixel precision: %d" % bits_per_pixel)


def resolve_inside_workspace(
    raw: Any,
    base: Path,
    workspace: Path,
    must_exist: bool = True,
) -> Path:
    root = workspace.resolve()
    candidate = Path(str(raw))
    path = (candidate if candidate.is_absolute() else base / candidate).resolve()
    if path != root and root not in path.parents:
        fail("Path must stay inside workspace: %s" % path)
    if must_exist and not path.is_file():
        fail("Required file does not exist: %s" % path)
    return path


def require_sha256(value: Any, label: str) -> str:
    digest = str(value or "").lower()
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        fail("%s must be a lowercase SHA-256" % label)
    return digest


def require_distinct_file_identities(
    named_paths: Sequence[Tuple[str, Path]],
) -> None:
    for left_index, (left_name, left_path) in enumerate(named_paths):
        for right_name, right_path in named_paths[left_index + 1 :]:
            if left_path == right_path:
                fail("Paths must be distinct: %s and %s" % (left_name, right_name))
            if left_path.exists() and right_path.exists():
                try:
                    same_file = os.path.samefile(str(left_path), str(right_path))
                except OSError as error:
                    raise ValueError(
                        "Cannot verify file identity for %s and %s" % (left_name, right_name)
                    ) from error
                if same_file:
                    fail(
                        "Paths must not be hard links to the same file: %s and %s"
                        % (left_name, right_name)
                    )


def finite_number(value: Any, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError("%s must be numeric" % label) from error
    if not math.isfinite(number):
        fail("%s must be finite" % label)
    return number


def parse_bbox(value: Any, label: str, size: Tuple[int, int]) -> Tuple[int, int, int, int]:
    if not isinstance(value, list) or len(value) != 4:
        fail("%s must be [x, y, width, height]" % label)
    if any(isinstance(item, bool) or not isinstance(item, int) for item in value):
        fail("%s coordinates must be integers" % label)
    x, y, box_width, box_height = value
    image_width, image_height = size
    if (
        x < 0
        or y < 0
        or box_width <= 0
        or box_height <= 0
        or x + box_width > image_width
        or y + box_height > image_height
    ):
        fail("%s lies outside the source image or has zero area" % label)
    return x, y, x + box_width, y + box_height


def bbox_from_record(record: Any, label: str, size: Tuple[int, int]) -> Tuple[int, int, int, int]:
    if isinstance(record, dict):
        return parse_bbox(record.get("bbox_px"), label, size)
    return parse_bbox(record, label, size)


def pixel_in_bbox(x: int, y: int, bbox: Tuple[int, int, int, int]) -> bool:
    return bbox[0] <= x < bbox[2] and bbox[1] <= y < bbox[3]


def iter_mask_pixels(mask: Image.Image) -> Iterable[Tuple[int, int]]:
    pixels = mask.load()
    width, height = mask.size
    for y in range(height):
        for x in range(width):
            if pixels[x, y] == 255:
                yield x, y


def load_binary_mask(path: Path, size: Tuple[int, int]) -> Image.Image:
    with Image.open(str(path)) as opened:
        if opened.mode not in {"1", "L"}:
            fail("Mask must use mode 1 or L: %s" % path)
        mask = opened.convert("L")
    if mask.size != size:
        fail("Mask dimensions do not match source: %s" % path)
    values = set(mask.tobytes())
    if not values or not values.issubset({0, 255}) or 255 not in values:
        fail("Mask must be non-empty and binary (0/255): %s" % path)
    return mask


def parse_color(value: Any) -> Tuple[int, int, int, int]:
    if not isinstance(value, list) or len(value) not in {3, 4}:
        fail("solid_fill.color_rgba must contain three or four integers")
    if any(isinstance(item, bool) or not isinstance(item, int) or item < 0 or item > 255 for item in value):
        fail("solid_fill.color_rgba entries must be integers from 0 to 255")
    rgba = list(value)
    if len(rgba) == 3:
        rgba.append(255)
    return tuple(rgba)  # type: ignore[return-value]


def region_pixel_count(mask: Image.Image) -> int:
    return mask.tobytes().count(255)


def protected_collision(
    mask: Image.Image,
    protected: Sequence[Tuple[int, int, int, int]],
) -> Optional[Tuple[int, int]]:
    for x, y in iter_mask_pixels(mask):
        if any(pixel_in_bbox(x, y, bbox) for bbox in protected):
            return x, y
    return None


def external_ring_samples(
    source: Image.Image,
    union_mask: Image.Image,
    protected: Sequence[Tuple[int, int, int, int]],
    bbox: Tuple[int, int, int, int],
    ring_px: int,
) -> List[Tuple[int, int, int, int]]:
    x0, y0, x1, y1 = bbox
    width, height = source.size
    left = max(0, x0 - ring_px)
    top = max(0, y0 - ring_px)
    right = min(width, x1 + ring_px)
    bottom = min(height, y1 + ring_px)
    source_pixels = source.load()
    mask_pixels = union_mask.load()
    samples: List[Tuple[int, int, int, int]] = []
    for y in range(top, bottom):
        for x in range(left, right):
            if x0 <= x < x1 and y0 <= y < y1:
                continue
            if mask_pixels[x, y] != 0:
                continue
            if any(pixel_in_bbox(x, y, protected_bbox) for protected_bbox in protected):
                continue
            samples.append(source_pixels[x, y])
    if not samples:
        fail("border_median has no eligible external ring samples")
    return samples


def channel_stddev(samples: Sequence[Tuple[int, int, int, int]]) -> List[float]:
    values: List[float] = []
    for channel in range(4):
        channel_values = [sample[channel] for sample in samples]
        values.append(statistics.pstdev(channel_values) if len(channel_values) > 1 else 0.0)
    return values


def channel_median(samples: Sequence[Tuple[int, int, int, int]]) -> Tuple[int, int, int, int]:
    return tuple(int(round(statistics.median([sample[channel] for sample in samples]))) for channel in range(4))  # type: ignore[return-value]


def validate_linear_boundaries(
    source: Image.Image,
    union_mask: Image.Image,
    protected: Sequence[Tuple[int, int, int, int]],
    bbox: Tuple[int, int, int, int],
    orientation: str,
    max_delta: float,
) -> float:
    pixels = source.load()
    mask_pixels = union_mask.load()
    x0, y0, x1, y1 = bbox
    width, height = source.size
    deltas: List[float] = []
    if orientation == "horizontal":
        if x0 == 0 or x1 >= width:
            fail("horizontal_linear requires one source pixel on both bbox sides")
        for y in range(y0, y1):
            sample_points = ((x0 - 1, y), (x1, y))
            if any(mask_pixels[x, y] != 0 for x, y in sample_points):
                fail("horizontal_linear boundary samples intersect a cleanup mask")
            if any(any(pixel_in_bbox(x, y, item) for item in protected) for x, y in sample_points):
                fail("horizontal_linear boundary samples intersect a protected region")
            left = pixels[x0 - 1, y]
            right = pixels[x1, y]
            deltas.append(max(abs(left[channel] - right[channel]) for channel in range(4)))
    else:
        if y0 == 0 or y1 >= height:
            fail("vertical_linear requires one source pixel above and below the bbox")
        for x in range(x0, x1):
            sample_points = ((x, y0 - 1), (x, y1))
            if any(mask_pixels[x, y] != 0 for x, y in sample_points):
                fail("vertical_linear boundary samples intersect a cleanup mask")
            if any(any(pixel_in_bbox(x, y, item) for item in protected) for x, y in sample_points):
                fail("vertical_linear boundary samples intersect a protected region")
            top = pixels[x, y0 - 1]
            bottom = pixels[x, y1]
            deltas.append(max(abs(top[channel] - bottom[channel]) for channel in range(4)))
    observed = max(deltas) if deltas else 0.0
    if observed > max_delta:
        fail("%s_linear boundary delta %.3f exceeds %.3f" % (orientation, observed, max_delta))
    return observed


def apply_method(
    output: Image.Image,
    source: Image.Image,
    mask: Image.Image,
    union_mask: Image.Image,
    protected: Sequence[Tuple[int, int, int, int]],
    bbox: Tuple[int, int, int, int],
    method: str,
    parameters: Dict[str, Any],
) -> Dict[str, Any]:
    output_pixels = output.load()
    source_pixels = source.load()
    x0, y0, x1, y1 = bbox
    method_audit: Dict[str, Any] = {"method": method}

    if method == "solid_fill":
        color = parse_color(parameters.get("color_rgba"))
        for x, y in iter_mask_pixels(mask):
            output_pixels[x, y] = color
        method_audit["color_rgba"] = list(color)
        return method_audit

    if method == "border_median":
        ring_px = int(parameters.get("ring_px", 2))
        if ring_px < 1 or ring_px > 64:
            fail("border_median.ring_px must be from 1 to 64")
        maximum = finite_number(parameters.get("max_border_stddev", 6.0), "max_border_stddev")
        if maximum < 0:
            fail("max_border_stddev must be non-negative")
        samples = external_ring_samples(source, union_mask, protected, bbox, ring_px)
        deviations = channel_stddev(samples)
        if max(deviations) > maximum:
            fail("border_median texture variance exceeds max_border_stddev")
        color = channel_median(samples)
        for x, y in iter_mask_pixels(mask):
            output_pixels[x, y] = color
        method_audit.update({
            "ring_px": ring_px,
            "sample_count": len(samples),
            "channel_stddev": [round(value, 6) for value in deviations],
            "fill_rgba": list(color),
        })
        return method_audit

    maximum_delta = finite_number(parameters.get("max_boundary_delta", 64.0), "max_boundary_delta")
    if maximum_delta < 0:
        fail("max_boundary_delta must be non-negative")
    orientation = "horizontal" if method == "horizontal_linear" else "vertical"
    observed_delta = validate_linear_boundaries(
        source, union_mask, protected, bbox, orientation, maximum_delta
    )
    if orientation == "horizontal":
        denominator = float(x1 - (x0 - 1))
        for x, y in iter_mask_pixels(mask):
            left = source_pixels[x0 - 1, y]
            right = source_pixels[x1, y]
            t = (x - (x0 - 1)) / denominator
            output_pixels[x, y] = tuple(int(round(left[channel] * (1.0 - t) + right[channel] * t)) for channel in range(4))
    else:
        denominator = float(y1 - (y0 - 1))
        for x, y in iter_mask_pixels(mask):
            top = source_pixels[x, y0 - 1]
            bottom = source_pixels[x, y1]
            t = (y - (y0 - 1)) / denominator
            output_pixels[x, y] = tuple(int(round(top[channel] * (1.0 - t) + bottom[channel] * t)) for channel in range(4))
    method_audit.update({
        "max_boundary_delta": maximum_delta,
        "observed_boundary_delta": observed_delta,
    })
    return method_audit


def png_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=False, compress_level=9)
    return buffer.getvalue()


def atomic_write_bytes(path: Path, payload: bytes, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError("Refusing to overwrite: %s" % path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".%s." % path.name, suffix=".tmp", dir=str(path.parent)
    )
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


def apply_cleanup_plan(
    plan_path: Path,
    workspace: Optional[Path] = None,
    force: bool = False,
) -> Dict[str, Any]:
    workspace = (workspace or Path.cwd()).resolve()
    plan_path = resolve_inside_workspace(plan_path, Path.cwd(), workspace)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if not isinstance(plan, dict):
        fail("Plan root must be an object")
    if plan.get("schema_version") != SCHEMA_VERSION:
        fail("schema_version must be %s" % SCHEMA_VERSION)
    if plan.get("scientific_evidence") is not False:
        fail("scientific_evidence must be explicitly false")
    if plan.get("risk_class") != "non_evidence_flat_background":
        fail("risk_class must be non_evidence_flat_background")
    if plan.get("approval_status") != "approved":
        fail("approval_status must be approved before cleanup")
    if not str(plan.get("approved_by", "")).strip() or not str(plan.get("approval_note", "")).strip():
        fail("approved_by and approval_note are required")

    base = plan_path.parent
    source_path = resolve_inside_workspace(plan.get("source_image"), base, workspace)
    if source_path.suffix.lower() not in LOSSLESS_SOURCE_SUFFIXES:
        fail("source_image must use a supported lossless raster format")
    expected_source_hash = require_sha256(plan.get("source_sha256"), "source_sha256")
    actual_source_hash = sha256_file(source_path)
    if actual_source_hash != expected_source_hash:
        fail("source_sha256 does not match source_image")

    output_path = resolve_inside_workspace(plan.get("output_image"), base, workspace, must_exist=False)
    mask_output_path = resolve_inside_workspace(plan.get("combined_mask_output"), base, workspace, must_exist=False)
    audit_path = resolve_inside_workspace(plan.get("audit_output"), base, workspace, must_exist=False)
    if output_path.suffix.lower() != ".png" or mask_output_path.suffix.lower() != ".png" or audit_path.suffix.lower() != ".json":
        fail("output_image and combined_mask_output must be PNG; audit_output must be JSON")
    output_targets = {output_path, mask_output_path, audit_path}
    if len(output_targets) != 3 or source_path in output_targets or plan_path in output_targets:
        fail("Source and output paths must be distinct")
    if not force:
        existing = [str(path) for path in output_targets if path.exists()]
        if existing:
            raise FileExistsError("Refusing to overwrite: %s" % ", ".join(sorted(existing)))

    named_paths: List[Tuple[str, Path]] = [
        ("plan", plan_path),
        ("source", source_path),
        ("output_image", output_path),
        ("combined_mask_output", mask_output_path),
        ("audit_output", audit_path),
    ]
    require_distinct_file_identities(named_paths)

    with Image.open(str(source_path)) as opened:
        if getattr(opened, "n_frames", 1) != 1:
            fail("source_image must contain exactly one raster frame")
        if opened.mode not in SUPPORTED_8BIT_MODES:
            fail(
                "source_image must use a supported 8-bit mode; refusing implicit mode/bit-depth conversion from %s"
                % opened.mode
            )
        validate_source_precision(opened, source_path)
        source = opened.convert("RGBA")
    size = source.size
    protected_raw = plan.get("protected_regions", [])
    if not isinstance(protected_raw, list):
        fail("protected_regions must be a list")
    protected = [bbox_from_record(record, "protected_regions[%d]" % index, size) for index, record in enumerate(protected_raw)]

    region_records = plan.get("regions")
    if not isinstance(region_records, list) or not region_records:
        fail("regions must be a non-empty list")
    identifiers = set()
    union_mask = Image.new("L", size, 0)
    union_pixels = union_mask.load()
    loaded_regions: List[Tuple[Dict[str, Any], Path, Image.Image, Tuple[int, int, int, int]]] = []
    for index, raw_region in enumerate(region_records):
        if not isinstance(raw_region, dict):
            fail("regions[%d] must be an object" % index)
        identifier = str(raw_region.get("id", "")).strip()
        if not identifier or identifier in identifiers:
            fail("Every cleanup region requires a unique non-empty id")
        identifiers.add(identifier)
        method = str(raw_region.get("method", ""))
        if method not in ALLOWED_METHODS:
            fail("Unsupported cleanup method for %s" % identifier)
        bbox = parse_bbox(raw_region.get("bbox_px"), "%s.bbox_px" % identifier, size)
        mask_path = resolve_inside_workspace(raw_region.get("mask_file"), base, workspace)
        if mask_path in output_targets or mask_path == plan_path:
            fail("Source masks, plan, and output paths must be distinct")
        expected_mask_hash = require_sha256(raw_region.get("mask_sha256"), "%s.mask_sha256" % identifier)
        if sha256_file(mask_path) != expected_mask_hash:
            fail("mask_sha256 does not match for %s" % identifier)
        mask = load_binary_mask(mask_path, size)
        collision = protected_collision(mask, protected)
        if collision is not None:
            fail("Cleanup mask %s intersects a protected region at %s" % (identifier, collision))
        mask_pixels = mask.load()
        for x, y in iter_mask_pixels(mask):
            if not pixel_in_bbox(x, y, bbox):
                fail("Cleanup mask %s has pixels outside bbox_px" % identifier)
            if union_pixels[x, y] != 0:
                fail("Cleanup masks overlap at (%d, %d)" % (x, y))
            union_pixels[x, y] = 255
        loaded_regions.append((raw_region, mask_path, mask, bbox))
        named_paths.append(("mask:%s" % identifier, mask_path))

    require_distinct_file_identities(named_paths)

    total_pixels = size[0] * size[1]
    mask_pixels_total = region_pixel_count(union_mask)
    maximum_fraction = finite_number(plan.get("max_mask_area_fraction", 0.02), "max_mask_area_fraction")
    if maximum_fraction <= 0 or maximum_fraction > 1:
        fail("max_mask_area_fraction must be in (0, 1]")
    mask_fraction = mask_pixels_total / float(total_pixels)
    if mask_fraction > maximum_fraction:
        fail("Combined cleanup mask exceeds max_mask_area_fraction")

    output = source.copy()
    audits: List[Dict[str, Any]] = []
    for raw_region, mask_path, mask, bbox in loaded_regions:
        before = output.copy()
        method = str(raw_region["method"])
        parameters = raw_region.get("parameters", {})
        if not isinstance(parameters, dict):
            fail("parameters must be an object for %s" % raw_region["id"])
        method_audit = apply_method(output, source, mask, union_mask, protected, bbox, method, parameters)
        before_pixels = before.load()
        output_pixels = output.load()
        changed = sum(1 for x, y in iter_mask_pixels(mask) if before_pixels[x, y] != output_pixels[x, y])
        if changed == 0:
            fail("Cleanup region %s changed no pixels" % raw_region["id"])
        audits.append({
            "id": raw_region["id"],
            "bbox_px": list(raw_region["bbox_px"]),
            "bbox_bounds_px": list(bbox),
            "mask_file": str(mask_path),
            "mask_sha256": sha256_file(mask_path),
            "masked_pixels": region_pixel_count(mask),
            "changed_pixels": changed,
            "method": method_audit,
        })

    source_pixels = source.load()
    output_pixels = output.load()
    union_values = union_mask.load()
    outside_changed = 0
    inside_changed = 0
    for y in range(size[1]):
        for x in range(size[0]):
            if source_pixels[x, y] != output_pixels[x, y]:
                if union_values[x, y] == 0:
                    outside_changed += 1
                else:
                    inside_changed += 1
    if outside_changed != 0:
        fail("Internal safety error: pixels outside the cleanup mask changed")
    if inside_changed == 0:
        fail("Cleanup produced no decoded pixel changes")

    output_payload = png_bytes(output)
    mask_payload = png_bytes(union_mask)
    audit: Dict[str, Any] = {
        "schema_version": "safe-text-cleanup-audit-v1",
        "plan": str(plan_path),
        "plan_sha256": sha256_file(plan_path),
        "source_image": str(source_path),
        "source_sha256": actual_source_hash,
        "source_decoded_rgba_sha256": decoded_rgba_sha256(source),
        "output_image": str(output_path),
        "output_sha256": sha256_bytes(output_payload),
        "output_decoded_rgba_sha256": decoded_rgba_sha256(output),
        "combined_mask_output": str(mask_output_path),
        "combined_mask_sha256": sha256_bytes(mask_payload),
        "audit_output": str(audit_path),
        "image_size_px": list(size),
        "masked_pixels": mask_pixels_total,
        "mask_area_fraction": mask_fraction,
        "changed_pixels_inside_mask": inside_changed,
        "changed_pixels_outside_mask": outside_changed,
        "outside_mask_pixel_identity": outside_changed == 0,
        "scientific_evidence": False,
        "risk_class": plan["risk_class"],
        "approval_status": plan["approval_status"],
        "approved_by": plan["approved_by"],
        "approval_note": plan["approval_note"],
        "protected_regions": protected_raw,
        "protected_region_bounds_px": [list(bbox) for bbox in protected],
        "regions": audits,
        "manual_visual_review_required": True,
        "publication_ready": False,
        "publication_blockers": [
            "manual 200%-400% halo and residue review not recorded",
            "live-text replacement and final composite not audited by this executor",
        ],
    }
    audit_payload = (json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    atomic_write_bytes(output_path, output_payload, force)
    atomic_write_bytes(mask_output_path, mask_payload, force)
    atomic_write_bytes(audit_path, audit_payload, force)
    return audit


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path, help="safe-text-cleanup-v1 JSON plan")
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--force", action="store_true", help="replace declared output files")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    audit = apply_cleanup_plan(args.plan, workspace=args.workspace, force=args.force)
    print(json.dumps({
        "output_image": audit["output_image"],
        "combined_mask_output": audit["combined_mask_output"],
        "audit_output": audit["audit_output"],
        "changed_pixels_outside_mask": audit["changed_pixels_outside_mask"],
        "publication_ready": audit["publication_ready"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
