from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from PIL import Image


SCHEMA_VERSION = "text-detection-manifest-v1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ENGINE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_inside_workspace(
    raw: str,
    workspace: Path,
    *,
    base: Optional[Path] = None,
    must_exist: bool = True,
) -> Path:
    workspace = workspace.resolve()
    requested = Path(raw)
    anchor = base.resolve() if base is not None else workspace
    path = (requested if requested.is_absolute() else anchor / requested).resolve()
    if path != workspace and workspace not in path.parents:
        raise ValueError("Path must stay inside workspace: %s" % path)
    if must_exist and not path.is_file():
        raise FileNotFoundError(path)
    return path


def resolve_workspace_root(raw: str) -> Path:
    """Resolve the caller-declared confinement root before any input is opened."""
    workspace = Path(str(raw)).resolve(strict=True)
    if not workspace.is_dir():
        raise NotADirectoryError("Workspace is not a directory: %s" % workspace)
    return workspace


def workspace_path(path: Path, workspace: Path) -> str:
    return path.resolve().relative_to(workspace.resolve()).as_posix()


def normalized_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).strip().split()).casefold()


def finite_number(value: Any, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError("%s must be numeric" % label)
    if not math.isfinite(number):
        raise ValueError("%s must be finite" % label)
    return number


def generic_confidence_01(value: Any) -> float:
    confidence = finite_number(value, "confidence")
    if confidence > 1.0:
        confidence /= 100.0
    if confidence < 0.0 or confidence > 1.0:
        raise ValueError("confidence must be in 0..1 or 0..100")
    return confidence


def tesseract_confidence_01(value: Any) -> float:
    confidence = finite_number(value, "Tesseract confidence")
    if confidence < 0.0 or confidence > 100.0:
        raise ValueError("Tesseract confidence must be in 0..100")
    return confidence / 100.0


def bbox_from_value(value: Any) -> Tuple[float, float, float, float]:
    if isinstance(value, dict):
        x = value.get("x", value.get("left"))
        y = value.get("y", value.get("top"))
        width = value.get("width", value.get("w"))
        height = value.get("height", value.get("h"))
        raw = (x, y, width, height)
    elif isinstance(value, (list, tuple)) and len(value) == 4:
        raw = tuple(value)
    else:
        raise ValueError("bbox must be [x, y, width, height] or an object")
    x, y, width, height = (
        finite_number(raw[0], "bbox.x"),
        finite_number(raw[1], "bbox.y"),
        finite_number(raw[2], "bbox.width"),
        finite_number(raw[3], "bbox.height"),
    )
    if x < 0 or y < 0 or width <= 0 or height <= 0:
        raise ValueError("bbox must have non-negative origin and positive size")
    return x, y, width, height


def polygon_from_value(value: Any) -> List[List[float]]:
    if not isinstance(value, list) or len(value) < 3:
        raise ValueError("polygon must contain at least three points")
    points: List[List[float]] = []
    for index, point in enumerate(value):
        if isinstance(point, dict):
            raw_x, raw_y = point.get("x"), point.get("y")
        elif isinstance(point, (list, tuple)) and len(point) == 2:
            raw_x, raw_y = point
        else:
            raise ValueError("polygon point %d must be [x, y] or an object" % index)
        points.append(
            [finite_number(raw_x, "polygon.x"), finite_number(raw_y, "polygon.y")]
        )
    return points


def bbox_from_polygon(points: Sequence[Sequence[float]]) -> Tuple[float, float, float, float]:
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    left, top, right, bottom = min(xs), min(ys), max(xs), max(ys)
    if right <= left or bottom <= top:
        raise ValueError("polygon must span a positive area")
    return left, top, right - left, bottom - top


def bbox_matches_polygon(
    bbox: Sequence[float], polygon_bbox: Sequence[float]
) -> bool:
    scale = max(bbox[2], bbox[3], polygon_bbox[2], polygon_bbox[3])
    tolerance = max(1.0, 0.02 * scale)
    return all(abs(left - right) <= tolerance for left, right in zip(bbox, polygon_bbox))


def rectangle_polygon(bbox: Sequence[float]) -> List[List[float]]:
    x, y, width, height = bbox
    return [[x, y], [x + width, y], [x + width, y + height], [x, y + height]]


def validate_geometry(
    bbox: Sequence[float], polygon: Sequence[Sequence[float]], image_size: Tuple[int, int]
) -> None:
    width_px, height_px = image_size
    x, y, width, height = bbox
    epsilon = 1e-6
    if x + width > width_px + epsilon or y + height > height_px + epsilon:
        raise ValueError("bbox falls outside source image")
    for point in polygon:
        if (
            point[0] < -epsilon
            or point[1] < -epsilon
            or point[0] > width_px + epsilon
            or point[1] > height_px + epsilon
        ):
            raise ValueError("polygon falls outside source image")


def bbox_json(bbox: Sequence[float]) -> Dict[str, float]:
    return {
        "x": bbox[0],
        "y": bbox[1],
        "width": bbox[2],
        "height": bbox[3],
    }


def bbox_iou(left: Sequence[float], right: Sequence[float]) -> float:
    left_x2, left_y2 = left[0] + left[2], left[1] + left[3]
    right_x2, right_y2 = right[0] + right[2], right[1] + right[3]
    intersection_width = max(0.0, min(left_x2, right_x2) - max(left[0], right[0]))
    intersection_height = max(0.0, min(left_y2, right_y2) - max(left[1], right[1]))
    intersection = intersection_width * intersection_height
    union = left[2] * left[3] + right[2] * right[3] - intersection
    return intersection / union if union > 0 else 0.0


@dataclass
class RawDetection:
    engine: str
    import_path: str
    import_sha256: str
    source_detection_id: str
    text: str
    confidence: float
    bbox: Tuple[float, float, float, float]
    polygon: List[List[float]]
    rotation_deg: float

    @property
    def normalized_text(self) -> str:
        return normalized_text(self.text)


def engine_and_path(raw: str, default_engine: str) -> Tuple[str, str]:
    if "=" in raw:
        engine, path = raw.split("=", 1)
    else:
        engine, path = default_engine, raw
    engine = engine.strip()
    path = path.strip()
    if not ENGINE_RE.fullmatch(engine):
        raise ValueError("Invalid engine name: %s" % engine)
    if not path:
        raise ValueError("OCR import path is empty")
    return engine, path


def resolved_import_paths(
    workspace: Path,
    tesseract_specs: Sequence[str],
    generic_specs: Sequence[str],
) -> List[Path]:
    paths: List[Path] = []
    for raw in tesseract_specs:
        _, raw_path = engine_and_path(raw, "tesseract")
        paths.append(resolve_inside_workspace(raw_path, workspace))
    for raw in generic_specs:
        if "=" in raw:
            _, raw_path = engine_and_path(raw, "generic")
        else:
            raw_path = raw
        paths.append(resolve_inside_workspace(raw_path, workspace))
    return paths


def refuse_input_overwrite(output: Path, source: Path, imports: Sequence[Path]) -> None:
    output = output.resolve()
    protected = [source.resolve()] + [path.resolve() for path in imports]
    if output in protected:
        raise ValueError("Output manifest must not overwrite a source or OCR import: %s" % output)


def read_tesseract_tsv(
    path: Path,
    engine: str,
    image_size: Tuple[int, int],
    workspace: Path,
) -> Tuple[List[RawDetection], Dict[str, Any]]:
    import_hash = sha256_file(path)
    detections: List[RawDetection] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        required = {"left", "top", "width", "height", "conf", "text"}
        if reader.fieldnames is None or not required.issubset(set(reader.fieldnames)):
            raise ValueError("Tesseract TSV is missing required columns")
        for row_number, row in enumerate(reader, start=2):
            text = str(row.get("text") or "").strip()
            if not text:
                continue
            raw_confidence = finite_number(row.get("conf"), "TSV conf at row %d" % row_number)
            if raw_confidence < 0:
                continue
            bbox = bbox_from_value(
                [row.get("left"), row.get("top"), row.get("width"), row.get("height")]
            )
            polygon = rectangle_polygon(bbox)
            validate_geometry(bbox, polygon, image_size)
            source_id = "tsv-row-%d" % row_number
            detections.append(
                RawDetection(
                    engine=engine,
                    import_path=workspace_path(path, workspace),
                    import_sha256=import_hash,
                    source_detection_id=source_id,
                    text=text,
                    confidence=tesseract_confidence_01(raw_confidence),
                    bbox=bbox,
                    polygon=polygon,
                    rotation_deg=0.0,
                )
            )
    return detections, {
        "engine": engine,
        "format": "tesseract-tsv",
        "path": workspace_path(path, workspace),
        "sha256": import_hash,
        "declared_source_sha256": None,
        "detection_count": len(detections),
    }


def generic_detection_list(payload: Any) -> List[Any]:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        raise ValueError("Generic JSON root must be an object or a list")
    for key in ("detections", "results", "items", "words"):
        if isinstance(payload.get(key), list):
            return payload[key]
    raise ValueError("Generic JSON must contain detections, results, items, or words")


def read_generic_json(
    path: Path,
    engine_override: Optional[str],
    image_size: Tuple[int, int],
    source_sha256: str,
    workspace: Path,
) -> Tuple[List[RawDetection], Dict[str, Any]]:
    import_hash = sha256_file(path)
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    payload_mapping = payload if isinstance(payload, dict) else {}
    engine_value = engine_override or payload_mapping.get("engine") or "generic"
    if not isinstance(engine_value, str) or not ENGINE_RE.fullmatch(engine_value.strip()):
        raise ValueError("Generic JSON requires a valid engine name")
    engine = engine_value.strip()
    declared_hash = payload_mapping.get("source_sha256")
    if declared_hash is not None:
        declared_hash = str(declared_hash).lower()
        if not SHA256_RE.fullmatch(declared_hash):
            raise ValueError("Generic JSON source_sha256 must be lowercase SHA-256")
        if declared_hash != source_sha256:
            raise ValueError("Generic JSON source_sha256 does not match source image")

    detections: List[RawDetection] = []
    for index, item in enumerate(generic_detection_list(payload), start=1):
        if not isinstance(item, dict):
            raise ValueError("Generic detection %d must be an object" % index)
        text_value = item.get("text", item.get("label", item.get("value")))
        if not isinstance(text_value, str) or not text_value.strip():
            raise ValueError("Generic detection %d has empty text" % index)
        confidence_value = item.get("confidence", item.get("conf", item.get("score")))
        if confidence_value is None:
            raise ValueError("Generic detection %d is missing confidence" % index)
        polygon_value = item.get("polygon_px", item.get("polygon", item.get("points")))
        bbox_value = item.get("bbox_px", item.get("bbox", item.get("box")))
        if polygon_value is None and bbox_value is None:
            raise ValueError("Generic detection %d is missing bbox/polygon" % index)
        polygon = polygon_from_value(polygon_value) if polygon_value is not None else []
        bbox = bbox_from_value(bbox_value) if bbox_value is not None else bbox_from_polygon(polygon)
        if polygon and bbox_value is not None:
            polygon_bbox = bbox_from_polygon(polygon)
            if not bbox_matches_polygon(bbox, polygon_bbox):
                raise ValueError(
                    "Generic detection %d bbox and polygon disagree" % index
                )
        if not polygon:
            polygon = rectangle_polygon(bbox)
        validate_geometry(bbox, polygon, image_size)
        rotation = finite_number(
            item.get("rotation_deg", item.get("rotation", item.get("angle", 0.0))),
            "rotation",
        )
        source_id = str(item.get("id", "json-item-%d" % index))
        if not source_id.strip():
            raise ValueError("Generic detection %d has an empty id" % index)
        detections.append(
            RawDetection(
                engine=engine,
                import_path=workspace_path(path, workspace),
                import_sha256=import_hash,
                source_detection_id=source_id,
                text=text_value.strip(),
                confidence=generic_confidence_01(confidence_value),
                bbox=bbox,
                polygon=polygon,
                rotation_deg=rotation,
            )
        )
    return detections, {
        "engine": engine,
        "format": "generic-json",
        "path": workspace_path(path, workspace),
        "sha256": import_hash,
        "declared_source_sha256": declared_hash,
        "detection_count": len(detections),
    }


def cluster_detections(
    detections: Sequence[RawDetection], iou_threshold: float
) -> List[List[RawDetection]]:
    clusters: List[List[RawDetection]] = []
    ordered = sorted(
        detections,
        key=lambda item: (
            item.bbox[1],
            item.bbox[0],
            item.normalized_text,
            item.engine,
            item.source_detection_id,
        ),
    )
    for detection in ordered:
        candidates: List[Tuple[float, int]] = []
        for index, cluster in enumerate(clusters):
            if cluster[0].normalized_text != detection.normalized_text:
                continue
            if detection.engine in {member.engine for member in cluster}:
                continue
            overlaps = [bbox_iou(member.bbox, detection.bbox) for member in cluster]
            minimum_overlap = min(overlaps)
            if minimum_overlap >= iou_threshold:
                candidates.append((minimum_overlap, index))
        if candidates:
            _, selected = max(candidates, key=lambda item: (item[0], -item[1]))
            clusters[selected].append(detection)
        else:
            clusters.append([detection])
    return clusters


def detection_manifest_item(
    index: int,
    cluster: Sequence[RawDetection],
    total_engines: int,
    confidence_threshold: float,
) -> Dict[str, Any]:
    representative = max(cluster, key=lambda item: item.confidence)
    engines = sorted({item.engine for item in cluster})
    reasons: List[str] = []
    if len(engines) < 2:
        reasons.append("single_engine_only")
    if representative.confidence < confidence_threshold:
        reasons.append("low_confidence")
    if any(abs(item.rotation_deg) > 1e-6 for item in cluster):
        reasons.append("rotated_text")
    contributors = [
        {
            "engine": item.engine,
            "import_path": item.import_path,
            "import_sha256": item.import_sha256,
            "source_detection_id": item.source_detection_id,
            "text": item.text,
            "confidence": item.confidence,
            "bbox_px": bbox_json(item.bbox),
            "polygon_px": item.polygon,
            "rotation_deg": item.rotation_deg,
        }
        for item in sorted(cluster, key=lambda value: (value.engine, value.source_detection_id))
    ]
    return {
        "id": "text-%04d" % index,
        "text": representative.text,
        "normalized_text": representative.normalized_text,
        "confidence": representative.confidence,
        "bbox_px": bbox_json(representative.bbox),
        "polygon_px": representative.polygon,
        "rotation_deg": representative.rotation_deg,
        "contributors": contributors,
        "engine_agreement": {
            "status": "multi-engine" if len(engines) >= 2 else "single-engine",
            "engine_count": len(engines),
            "total_imported_engines": total_engines,
            "engines": engines,
        },
        "manual_gate": {
            "required": bool(reasons),
            "status": "pending" if reasons else "not-required",
            "reasons": reasons,
        },
    }


def build_manifest(
    source: Path,
    workspace: Path,
    tesseract_specs: Sequence[str],
    generic_specs: Sequence[str],
    *,
    iou_threshold: float = 0.5,
    confidence_threshold: float = 0.85,
) -> Dict[str, Any]:
    workspace = workspace.resolve()
    source = resolve_inside_workspace(str(source), workspace)
    if iou_threshold <= 0 or iou_threshold > 1:
        raise ValueError("iou_threshold must be in (0, 1]")
    if confidence_threshold < 0 or confidence_threshold > 1:
        raise ValueError("confidence_threshold must be in [0, 1]")
    if not tesseract_specs and not generic_specs:
        raise ValueError("At least one imported OCR result is required")

    source_hash = sha256_file(source)
    with Image.open(str(source)) as image:
        image.verify()
    with Image.open(str(source)) as image:
        image_size = image.size
        source_format = image.format

    raw_detections: List[RawDetection] = []
    imports: List[Dict[str, Any]] = []
    seen_import_paths = set()
    seen_import_hashes = set()

    def register_import(metadata: Dict[str, Any]) -> None:
        import_path = metadata["path"]
        import_hash = metadata["sha256"]
        if import_path in seen_import_paths or import_hash in seen_import_hashes:
            raise ValueError("Duplicate OCR import source is not allowed")
        seen_import_paths.add(import_path)
        seen_import_hashes.add(import_hash)
        imports.append(metadata)

    for raw in tesseract_specs:
        engine, raw_path = engine_and_path(raw, "tesseract")
        path = resolve_inside_workspace(raw_path, workspace)
        records, metadata = read_tesseract_tsv(path, engine, image_size, workspace)
        raw_detections.extend(records)
        register_import(metadata)
    for raw in generic_specs:
        if "=" in raw:
            engine_override, raw_path = engine_and_path(raw, "generic")
        else:
            engine_override, raw_path = None, raw
        path = resolve_inside_workspace(raw_path, workspace)
        records, metadata = read_generic_json(
            path, engine_override, image_size, source_hash, workspace
        )
        raw_detections.extend(records)
        register_import(metadata)
    if not raw_detections:
        raise ValueError("Imported OCR results contain no usable text detections")

    engines = sorted({item.engine for item in raw_detections})
    clusters = cluster_detections(raw_detections, iou_threshold)
    manifest_detections = [
        detection_manifest_item(index, cluster, len(engines), confidence_threshold)
        for index, cluster in enumerate(clusters, start=1)
    ]
    pending_count = sum(
        1 for item in manifest_detections if item["manual_gate"]["required"]
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "path": workspace_path(source, workspace),
            "sha256": source_hash,
            "width_px": image_size[0],
            "height_px": image_size[1],
            "format": source_format,
        },
        "imports": imports,
        "matching": {
            "method": "normalized-text-and-bbox-iou",
            "bbox_iou_threshold": iou_threshold,
            "confidence_manual_gate_threshold": confidence_threshold,
        },
        "detections": manifest_detections,
        "manual_gate": {
            "required": True,
            "status": "pending",
            "reason": "human_confirmation_required_before_cleanup_or_replacement",
            "pending_detection_count": pending_count,
            "total_detection_count": len(manifest_detections),
        },
        "read_only_import": True,
        "ocr_runtime_invoked": False,
        "cleanup_authorized": False,
        "publication_ready": False,
    }


def atomic_write_json(path: Path, payload: Dict[str, Any], force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError("Output already exists; use --force explicitly: %s" % path)
    if not path.parent.is_dir():
        raise FileNotFoundError("Output parent directory does not exist: %s" % path.parent)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".%s." % path.name, suffix=".tmp", dir=str(path.parent)
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(str(temporary_path), str(path))
    except Exception:
        if temporary_path.exists():
            temporary_path.unlink()
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a hash-bound, review-gated manifest from existing OCR exports."
    )
    parser.add_argument("source_image", help="Source raster image")
    parser.add_argument("output_manifest", help="New JSON manifest path")
    parser.add_argument("--workspace", default=".", help="Workspace confinement root")
    parser.add_argument(
        "--tesseract-tsv",
        action="append",
        default=[],
        metavar="[ENGINE=]PATH",
        help="Import an existing Tesseract TSV; repeat as needed",
    )
    parser.add_argument(
        "--generic-json",
        action="append",
        default=[],
        metavar="[ENGINE=]PATH",
        help="Import normalized generic JSON; repeat as needed",
    )
    parser.add_argument("--iou-threshold", type=float, default=0.5)
    parser.add_argument("--confidence-threshold", type=float, default=0.85)
    parser.add_argument("--force", action="store_true", help="Explicitly replace output")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    workspace = resolve_workspace_root(args.workspace)
    source = resolve_inside_workspace(args.source_image, workspace)
    output = resolve_inside_workspace(
        args.output_manifest, workspace, must_exist=False
    )
    import_paths = resolved_import_paths(
        workspace, args.tesseract_tsv, args.generic_json
    )
    refuse_input_overwrite(output, source, import_paths)
    manifest = build_manifest(
        source,
        workspace,
        args.tesseract_tsv,
        args.generic_json,
        iou_threshold=args.iou_threshold,
        confidence_threshold=args.confidence_threshold,
    )
    atomic_write_json(output, manifest, args.force)
    print(json.dumps({"output": str(output), "detections": len(manifest["detections"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
