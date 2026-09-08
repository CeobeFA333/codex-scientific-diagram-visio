from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import tempfile
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


ID_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:-]*$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
URL_RE = re.compile(r"(?:https?://|file://|ftp://)", re.IGNORECASE)
TAG_RE = re.compile(r"<\s*/?\s*[A-Za-z][^>]*>")
ALLOWED_BACKENDS = {"visio_scenegraph", "drawio_mxgraph"}
COUNT_KEYS = {
    "total_objects",
    "text_objects",
    "vector_objects",
    "edge_objects",
    "connector_objects",
    "atomic_rasters",
}


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def resolve_inside_workspace(raw: str, base: Path, *, must_exist: bool = True) -> Path:
    workspace = Path.cwd().resolve()
    requested = Path(raw)
    path = (requested if requested.is_absolute() else base / requested).resolve()
    if path != workspace and workspace not in path.parents:
        raise ValueError("Path must stay inside workspace: %s" % path)
    if must_exist and not path.is_file():
        raise FileNotFoundError(path)
    return path


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def first_value(mapping: Dict[str, Any], keys: Sequence[str]) -> Any:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return None


def nested_mapping(mapping: Dict[str, Any], keys: Sequence[str]) -> Dict[str, Any]:
    value: Any = mapping
    for key in keys:
        if not isinstance(value, dict):
            return {}
        value = value.get(key)
    return value if isinstance(value, dict) else {}


def normalized_bool(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in {0, 1}:
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "verified", "passed"}:
            return True
        if lowered in {"false", "0", "no", "not-run", "failed", "pending"}:
            return False
    return None


def normalized_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def endpoint_id(value: Any) -> Optional[str]:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        candidate = first_value(
            value,
            ("id", "semantic_id", "semanticId", "shape_id", "shapeId", "object_id", "objectId"),
        )
        return str(candidate) if candidate is not None else None
    return None


def style_map(raw: str) -> Dict[str, str]:
    parsed: Dict[str, str] = {}
    for token in raw.split(";"):
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        parsed[key.strip()] = urllib.parse.unquote(value.strip())
    return parsed


def truthy_style(style: Dict[str, str], keys: Sequence[str]) -> bool:
    return any(normalized_bool(style.get(key)) is True for key in keys)


def active_external_reference(key: str, value: Any) -> bool:
    if not isinstance(value, str):
        return False
    lowered_key = key.lower().replace("-", "_")
    active = any(token in lowered_key for token in ("href", "url", "link", "src", "image"))
    if not active:
        return False
    stripped = urllib.parse.unquote(value.strip())
    if stripped.startswith("data:image/"):
        return False
    return bool(URL_RE.search(stripped)) or lowered_key in {"href", "src", "image"}


def json_external_issues(value: Any, path: str = "$") -> List[dict]:
    issues: List[dict] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child_path = "%s.%s" % (path, key)
            if isinstance(item, str) and "foreignobject" in item.lower():
                issues.append({"code": "foreign_object_present", "path": child_path})
            if active_external_reference(key, item):
                issues.append({"code": "external_reference_present", "path": child_path, "value": item})
            issues.extend(json_external_issues(item, child_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            issues.extend(json_external_issues(item, "%s[%d]" % (path, index)))
    return issues


@dataclass
class SceneObject:
    id: str
    kind: str
    text: Optional[str] = None
    font_family: Optional[str] = None
    font_size_pt: Optional[float] = None
    source_id: Optional[str] = None
    target_id: Optional[str] = None
    atomic: Optional[dict] = None


@dataclass
class ParsedScene:
    backend: str
    objects: List[SceneObject]
    width_mm: Optional[float]
    height_mm: Optional[float]
    declared_source_svg: Optional[str]
    declared_source_sha256: Optional[str]
    runtime_claim: Optional[bool]
    structural_issues: List[dict]


def candidate_object_lists(payload: dict) -> List[List[dict]]:
    candidates: List[Any] = [
        payload.get("objects"),
        payload.get("shapes"),
        payload.get("nodes"),
        nested_mapping(payload, ("scene",)).get("objects"),
        nested_mapping(payload, ("scene",)).get("shapes"),
        nested_mapping(payload, ("sceneGraph",)).get("objects"),
        nested_mapping(payload, ("sceneGraph",)).get("shapes"),
    ]
    pages = first_value(payload, ("pages",))
    if not isinstance(pages, list):
        pages = nested_mapping(payload, ("sceneGraph",)).get("pages")
    if isinstance(pages, list):
        for page in pages:
            if isinstance(page, dict):
                candidates.extend((page.get("objects"), page.get("shapes"), page.get("nodes")))
    return [value for value in candidates if isinstance(value, list)]


def collect_visio_records(payload: dict) -> List[dict]:
    records: List[dict] = []
    seen_containers = set()
    for values in candidate_object_lists(payload):
        marker = id(values)
        if marker in seen_containers:
            continue
        seen_containers.add(marker)
        records.extend(item for item in values if isinstance(item, dict))
    for key in ("connectors", "edges"):
        values = payload.get(key)
        if isinstance(values, list):
            records.extend(item for item in values if isinstance(item, dict))
    return records


def visio_text_fields(record: dict) -> Tuple[Optional[str], Optional[str], Optional[float]]:
    text_value = first_value(record, ("text", "label", "contents", "value"))
    text_mapping = text_value if isinstance(text_value, dict) else {}
    text = first_value(text_mapping, ("content", "text", "value")) if text_mapping else text_value
    style = record.get("style") if isinstance(record.get("style"), dict) else {}
    rich_text = record.get("rich_text") if isinstance(record.get("rich_text"), dict) else {}
    runs = rich_text.get("runs") if isinstance(rich_text.get("runs"), list) else []
    run_families = {
        str(first_value(run, ("font_family", "fontFamily", "font")))
        for run in runs
        if isinstance(run, dict) and first_value(run, ("font_family", "fontFamily", "font")) is not None
    }
    run_sizes = [
        normalized_float(first_value(run, ("font_size_pt", "fontSizePt", "font_size", "fontSize")))
        for run in runs
        if isinstance(run, dict)
    ]
    run_sizes = [value for value in run_sizes if value is not None]
    font_family = first_value(
        text_mapping,
        ("font_family", "fontFamily", "font"),
    ) or first_value(record, ("font_family", "fontFamily", "font")) or first_value(
        style, ("font_family", "fontFamily", "font")
    )
    if font_family is None and len(run_families) == 1:
        font_family = next(iter(run_families))
    elif font_family is None and len(run_families) > 1:
        font_family = ", ".join(sorted(run_families))
    font_size = first_value(text_mapping, ("font_size_pt", "fontSizePt", "font_size", "fontSize"))
    if font_size is None:
        font_size = first_value(record, ("font_size_pt", "fontSizePt", "font_size", "fontSize"))
    if font_size is None:
        font_size = first_value(style, ("font_size_pt", "fontSizePt", "font_size", "fontSize"))
    if font_size is None and run_sizes:
        # Scientific subscripts/superscripts are commonly smaller than the base
        # live type.  The largest run is the main type size; all run families are
        # still checked above so a fallback font cannot hide in a small run.
        font_size = max(run_sizes)
    return (
        str(text) if isinstance(text, (str, int, float)) and str(text) != "" else None,
        str(font_family) if font_family is not None else None,
        normalized_float(font_size),
    )


def visio_atomic_fields(record: dict) -> Optional[dict]:
    metadata = record.get("atomic_raster") if isinstance(record.get("atomic_raster"), dict) else {}
    style = record.get("style") if isinstance(record.get("style"), dict) else {}
    kind = str(first_value(record, ("kind", "type", "object_type", "objectType")) or "").lower()
    atomic_flag = normalized_bool(
        first_value(record, ("atomic_raster_unit", "atomicRasterUnit", "data_atomic_raster_unit"))
    )
    if atomic_flag is None:
        atomic_flag = normalized_bool(first_value(metadata, ("atomic_raster_unit", "atomicRasterUnit")))
    if atomic_flag is None:
        atomic_flag = normalized_bool(first_value(style, ("atomic_raster_unit", "atomicRasterUnit")))
    if atomic_flag is not True and kind not in {"atomic_raster", "atomic-raster", "evidence_image"}:
        return None
    combined = dict(style)
    combined.update(metadata)
    combined.update(record)
    return {
        "source_file": first_value(combined, ("source_file", "sourceFile", "data_source_file")),
        "source_sha256": first_value(
            combined, ("source_sha256", "sourceSha256", "data_source_sha256")
        ),
        "embedded_sha256": first_value(combined, ("embedded_sha256", "embeddedSha256")),
        "evidence": normalized_bool(first_value(combined, ("evidence", "data_evidence"))),
        "raster_reason": first_value(combined, ("raster_reason", "rasterReason")),
        "data_uri": first_value(combined, ("data_uri", "dataUri", "image_data", "imageData")),
    }


def parse_visio(path: Path, payload: dict, contract: dict) -> ParsedScene:
    issues = json_external_issues(payload)
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    page = payload.get("page") if isinstance(payload.get("page"), dict) else {}
    canvas = payload.get("canvas") if isinstance(payload.get("canvas"), dict) else {}
    if not page:
        pages = payload.get("pages")
        if isinstance(pages, list) and pages and isinstance(pages[0], dict):
            page = pages[0]
    width_mm = normalized_float(
        first_value(page, ("width_mm", "widthMm", "page_width_mm", "pageWidthMm"))
        or first_value(canvas, ("width_mm", "widthMm", "print_width_mm"))
        or first_value(metadata, ("canvas_width_mm", "canvasWidthMm"))
    )
    height_mm = normalized_float(
        first_value(page, ("height_mm", "heightMm", "page_height_mm", "pageHeightMm"))
        or first_value(canvas, ("height_mm", "heightMm", "print_height_mm"))
        or first_value(metadata, ("canvas_height_mm", "canvasHeightMm"))
    )
    if width_mm is None or height_mm is None:
        width_px = normalized_float(first_value(canvas, ("width_px", "widthPx")))
        height_px = normalized_float(first_value(canvas, ("height_px", "heightPx")))
        dpi = normalized_float(first_value(canvas, ("dpi", "pixels_per_inch", "pixelsPerInch")))
        if dpi is not None and dpi > 0:
            if width_mm is None and width_px is not None:
                width_mm = width_px * 25.4 / dpi
            if height_mm is None and height_px is not None:
                height_mm = height_px * 25.4 / dpi
    source_decl = first_value(metadata, ("source_svg", "sourceSvg")) or first_value(
        payload, ("source_svg", "sourceSvg")
    )
    source_path = source_decl.get("path") if isinstance(source_decl, dict) else source_decl
    source_hash = (
        first_value(source_decl, ("sha256", "source_svg_sha256"))
        if isinstance(source_decl, dict)
        else None
    )
    source_hash = source_hash or first_value(
        metadata, ("source_svg_sha256", "sourceSvgSha256")
    ) or first_value(payload, ("source_svg_sha256", "sourceSvgSha256"))
    runtime_claim = normalized_bool(
        first_value(metadata, ("backend_runtime_verified", "backendRuntimeVerified"))
        or first_value(payload, ("backend_runtime_verified", "backendRuntimeVerified"))
    )
    objects: List[SceneObject] = []
    for record in collect_visio_records(payload):
        object_id = first_value(
            record,
            ("id", "semantic_id", "semanticId", "object_id", "objectId", "shape_id", "shapeId"),
        )
        if object_id is None:
            issues.append({"code": "object_id_missing"})
            continue
        kind = str(first_value(record, ("kind", "type", "object_type", "objectType")) or "shape").lower()
        text, font_family, font_size = visio_text_fields(record)
        source_id = endpoint_id(first_value(record, ("source_id", "sourceId", "source", "from")))
        target_id = endpoint_id(first_value(record, ("target_id", "targetId", "target", "to")))
        is_connector = kind in {"connector", "edge", "link"} or source_id is not None or target_id is not None
        atomic = visio_atomic_fields(record)
        normalized_kind = "connector" if is_connector else ("atomic_raster" if atomic else kind)
        objects.append(
            SceneObject(
                id=str(object_id),
                kind=normalized_kind,
                text=text,
                font_family=font_family,
                font_size_pt=font_size,
                source_id=source_id,
                target_id=target_id,
                atomic=atomic,
            )
        )
    return ParsedScene(
        backend="visio_scenegraph",
        objects=objects,
        width_mm=width_mm,
        height_mm=height_mm,
        declared_source_svg=str(source_path) if source_path is not None else None,
        declared_source_sha256=str(source_hash).lower() if source_hash is not None else None,
        runtime_claim=runtime_claim,
        structural_issues=issues,
    )


def xml_attribute(elements: Iterable[ET.Element], keys: Sequence[str]) -> Optional[str]:
    for element in elements:
        for key in keys:
            if key in element.attrib:
                return element.attrib[key]
    return None


def drawio_cell_text(cell: ET.Element, style: Dict[str, str]) -> Tuple[Optional[str], Optional[str], Optional[float]]:
    value = cell.attrib.get("value", "")
    if not value:
        return None, None, None
    return value, style.get("fontFamily"), normalized_float(style.get("fontSize"))


def drawio_atomic_fields(cell: ET.Element, style: Dict[str, str]) -> Optional[dict]:
    attrs = cell.attrib
    atomic = truthy_style(style, ("atomicRasterUnit", "dataAtomicRasterUnit")) or normalized_bool(
        first_value(attrs, ("data-atomic-raster-unit", "atomicRasterUnit"))
    ) is True
    if not atomic:
        return None
    return {
        "source_file": first_value(attrs, ("data-source-file", "sourceFile"))
        or first_value(style, ("sourceFile", "dataSourceFile")),
        "source_sha256": first_value(attrs, ("data-source-sha256", "sourceSha256"))
        or first_value(style, ("sourceSha256", "dataSourceSha256")),
        "embedded_sha256": first_value(attrs, ("data-embedded-sha256", "embeddedSha256"))
        or first_value(style, ("embeddedSha256", "dataEmbeddedSha256")),
        "evidence": normalized_bool(first_value(attrs, ("data-evidence", "evidence")))
        if first_value(attrs, ("data-evidence", "evidence")) is not None
        else normalized_bool(first_value(style, ("evidence", "dataEvidence"))),
        "raster_reason": first_value(attrs, ("data-raster-reason", "rasterReason"))
        or first_value(style, ("rasterReason", "dataRasterReason")),
        "data_uri": first_value(attrs, ("data-uri", "imageData"))
        or first_value(style, ("image", "dataUri")),
    }


def parse_drawio(path: Path, root: ET.Element, contract: dict) -> ParsedScene:
    issues: List[dict] = []
    if any(local_name(element.tag).lower() == "foreignobject" for element in root.iter()):
        issues.append({"code": "foreign_object_present"})
    mxfiles = [element for element in root.iter() if local_name(element.tag) == "mxfile"]
    models = [element for element in root.iter() if local_name(element.tag) == "mxGraphModel"]
    diagrams = [element for element in root.iter() if local_name(element.tag) == "diagram"]
    if not models:
        if diagrams and any((diagram.text or "").strip() for diagram in diagrams):
            issues.append({"code": "compressed_drawio_payload_not_auditable"})
        else:
            issues.append({"code": "mxgraph_model_missing"})
    declaration_nodes = mxfiles + models
    source_path = xml_attribute(
        declaration_nodes,
        ("data-source-svg", "source-svg", "sourceSvg"),
    )
    source_hash = xml_attribute(
        declaration_nodes,
        ("data-source-svg-sha256", "source-svg-sha256", "sourceSvgSha256"),
    )
    runtime_claim = normalized_bool(
        xml_attribute(
            declaration_nodes,
            ("data-backend-runtime-verified", "backend-runtime-verified", "backendRuntimeVerified"),
        )
    )
    width_mm = normalized_float(
        xml_attribute(declaration_nodes, ("data-canvas-width-mm", "canvas-width-mm", "canvasWidthMm"))
    )
    height_mm = normalized_float(
        xml_attribute(declaration_nodes, ("data-canvas-height-mm", "canvas-height-mm", "canvasHeightMm"))
    )
    if (width_mm is None or height_mm is None) and models:
        page_width = normalized_float(models[0].attrib.get("pageWidth"))
        page_height = normalized_float(models[0].attrib.get("pageHeight"))
        unit = str(contract.get("canvas", {}).get("drawio_page_unit", "")).lower()
        dpi = normalized_float(contract.get("canvas", {}).get("drawio_dpi"))
        if unit == "pt":
            if page_width is not None:
                width_mm = page_width * 25.4 / 72.0
            if page_height is not None:
                height_mm = page_height * 25.4 / 72.0
        elif dpi:
            if page_width is not None:
                width_mm = page_width * 25.4 / dpi
            if page_height is not None:
                height_mm = page_height * 25.4 / dpi
    objects: List[SceneObject] = []
    cells = [element for element in root.iter() if local_name(element.tag) == "mxCell"]
    source_id_map = {
        cell.attrib["data-svg-id"]: cell.attrib["id"]
        for cell in cells
        if cell.attrib.get("data-svg-id") and cell.attrib.get("id")
    }
    for cell in cells:
        cell_id = cell.attrib.get("id")
        if not cell.attrib.get("vertex") and not cell.attrib.get("edge"):
            continue
        if cell_id is None:
            issues.append({"code": "object_id_missing"})
            continue
        style = style_map(cell.attrib.get("style", ""))
        html_enabled = normalized_bool(style.get("html")) is True
        value = cell.attrib.get("value", "")
        if html_enabled or TAG_RE.search(value) or "foreignobject" in value.lower():
            issues.append({"code": "drawio_html_text_forbidden", "id": cell_id})
        for key, raw in list(cell.attrib.items()) + list(style.items()):
            if active_external_reference(key, raw):
                issues.append(
                    {"code": "external_reference_present", "id": cell_id, "attribute": key, "value": raw}
                )
        text, font_family, font_size = drawio_cell_text(cell, style)
        source_id = cell.attrib.get("source")
        target_id = cell.attrib.get("target")
        if source_id is None and cell.attrib.get("data-source-svg-id"):
            source_id = source_id_map.get(cell.attrib["data-source-svg-id"])
        if target_id is None and cell.attrib.get("data-target-svg-id"):
            target_id = source_id_map.get(cell.attrib["data-target-svg-id"])
        is_edge = cell.attrib.get("edge") == "1"
        is_connector = source_id is not None or target_id is not None
        atomic = drawio_atomic_fields(cell, style)
        kind = "connector" if is_connector else ("edge" if is_edge else ("atomic_raster" if atomic else "shape"))
        objects.append(
            SceneObject(
                id=cell_id,
                kind=kind,
                text=text,
                font_family=font_family,
                font_size_pt=font_size,
                source_id=source_id,
                target_id=target_id,
                atomic=atomic,
            )
        )
    return ParsedScene(
        backend="drawio_mxgraph",
        objects=objects,
        width_mm=width_mm,
        height_mm=height_mm,
        declared_source_svg=source_path,
        declared_source_sha256=source_hash.lower() if source_hash else None,
        runtime_claim=runtime_claim,
        structural_issues=issues,
    )


def parse_scene(path: Path, contract: dict) -> ParsedScene:
    backend = contract.get("backend")
    if backend == "visio_scenegraph":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Visio SceneGraph must be a JSON object")
        return parse_visio(path, payload, contract)
    if backend == "drawio_mxgraph":
        return parse_drawio(path, ET.parse(path).getroot(), contract)
    raise ValueError("Unsupported backend: %s" % backend)


def validate_contract(contract: dict) -> None:
    required = {"schema_version", "backend", "source_svg", "canvas", "texts", "object_counts"}
    missing = sorted(required - set(contract))
    if missing:
        raise ValueError("Backend scene contract is missing: " + ", ".join(missing))
    if contract["backend"] not in ALLOWED_BACKENDS:
        raise ValueError("Unsupported backend")
    source = contract["source_svg"]
    if not isinstance(source, dict) or set(("path", "sha256")) - set(source):
        raise ValueError("source_svg must declare path and sha256")
    if not SHA256_RE.fullmatch(str(source["sha256"]).lower()):
        raise ValueError("source_svg.sha256 must be lowercase SHA-256")
    canvas = contract["canvas"]
    if not isinstance(canvas, dict) or not {"width_mm", "height_mm"}.issubset(canvas):
        raise ValueError("canvas must declare width_mm and height_mm")
    if any(normalized_float(canvas.get(key)) is None or float(canvas[key]) <= 0 for key in ("width_mm", "height_mm")):
        raise ValueError("canvas dimensions must be positive")
    if not isinstance(contract["texts"], list):
        raise ValueError("texts must be a list")
    for text in contract["texts"]:
        if not isinstance(text, dict) or not {"id", "text", "font_family", "font_size_pt"}.issubset(text):
            raise ValueError("each text contract needs id, text, font_family, and font_size_pt")
    counts = contract["object_counts"]
    if not isinstance(counts, dict) or not set(counts).issubset(COUNT_KEYS):
        raise ValueError("object_counts contains unsupported keys")
    if any(not isinstance(value, int) or value < 0 for value in counts.values()):
        raise ValueError("object_counts must be non-negative integers")
    if "connections" in contract and not isinstance(contract["connections"], list):
        raise ValueError("connections must be a list")
    if "atomic_rasters" in contract and not isinstance(contract["atomic_rasters"], list):
        raise ValueError("atomic_rasters must be a list")


def computed_counts(objects: Sequence[SceneObject]) -> Dict[str, int]:
    return {
        "total_objects": len(objects),
        "text_objects": sum(item.text is not None for item in objects),
        "vector_objects": sum(item.kind not in {"connector", "atomic_raster"} for item in objects),
        "edge_objects": sum(item.kind in {"connector", "edge"} for item in objects),
        "connector_objects": sum(item.kind == "connector" for item in objects),
        "atomic_rasters": sum(item.atomic is not None for item in objects),
    }


def decode_data_uri(raw: Any) -> Optional[bytes]:
    if not isinstance(raw, str):
        return None
    value = urllib.parse.unquote(raw)
    if not value.startswith("data:image/") or ";base64," not in value:
        return None
    try:
        return base64.b64decode(value.split(",", 1)[1], validate=True)
    except ValueError:
        return None


def audit_structure(scene: ParsedScene, scene_path: Path, contract: dict, contract_path: Path) -> Tuple[List[dict], dict]:
    issues = list(scene.structural_issues)
    ids = [item.id for item in scene.objects]
    duplicates = sorted({value for value in ids if ids.count(value) > 1})
    if duplicates:
        issues.append({"code": "duplicate_object_ids", "ids": duplicates})
    unstable = sorted({value for value in ids if not ID_RE.fullmatch(value)})
    if unstable:
        issues.append({"code": "unstable_object_ids", "ids": unstable})
    expected_width = float(contract["canvas"]["width_mm"])
    expected_height = float(contract["canvas"]["height_mm"])
    tolerance = float(contract["canvas"].get("tolerance_mm", 0.01))
    if scene.width_mm is None or scene.height_mm is None:
        issues.append({"code": "physical_canvas_metadata_missing"})
    elif abs(scene.width_mm - expected_width) > tolerance or abs(scene.height_mm - expected_height) > tolerance:
        issues.append(
            {
                "code": "physical_canvas_mismatch",
                "expected_mm": [expected_width, expected_height],
                "actual_mm": [scene.width_mm, scene.height_mm],
            }
        )

    source_contract = contract["source_svg"]
    source_path = resolve_inside_workspace(str(source_contract["path"]), contract_path.parent)
    actual_source_hash = sha256_file(source_path)
    expected_source_hash = str(source_contract["sha256"]).lower()
    declared_source_svg = scene.declared_source_svg
    declared_source_sha256 = scene.declared_source_sha256
    provenance_summary = None
    provenance_raw = contract.get("provenance_manifest")
    if provenance_raw:
        provenance_path = resolve_inside_workspace(str(provenance_raw), contract_path.parent)
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        provenance_summary = {"path": str(provenance_path), "sha256": sha256_file(provenance_path)}
        manifest_scene_raw = first_value(provenance, ("drawio", "scene", "scene_file", "sceneFile"))
        manifest_scene_hash = first_value(
            provenance, ("drawio_sha256", "scene_sha256", "sceneSha256")
        )
        if not manifest_scene_raw or not manifest_scene_hash:
            issues.append({"code": "provenance_manifest_scene_binding_missing"})
        else:
            try:
                manifest_scene = resolve_inside_workspace(str(manifest_scene_raw), provenance_path.parent)
            except (FileNotFoundError, ValueError) as exc:
                issues.append(
                    {"code": "provenance_manifest_scene_path_invalid", "detail": str(exc)}
                )
            else:
                if manifest_scene != scene_path or str(manifest_scene_hash).lower() != sha256_file(scene_path):
                    issues.append({"code": "provenance_manifest_scene_binding_mismatch"})
        manifest_source = first_value(provenance, ("source_svg", "sourceSvg"))
        manifest_source_hash = first_value(
            provenance, ("source_svg_sha256", "sourceSvgSha256")
        )
        if declared_source_svg is None:
            declared_source_svg = str(manifest_source) if manifest_source is not None else None
        if declared_source_sha256 is None:
            declared_source_sha256 = (
                str(manifest_source_hash).lower() if manifest_source_hash is not None else None
            )
    if actual_source_hash != expected_source_hash:
        issues.append(
            {"code": "source_svg_hash_mismatch", "expected": expected_source_hash, "actual": actual_source_hash}
        )
    if declared_source_sha256 != expected_source_hash:
        issues.append(
            {
                "code": "scene_source_svg_hash_declaration_mismatch",
                "expected": expected_source_hash,
                "actual": declared_source_sha256,
            }
        )
    if not declared_source_svg:
        issues.append({"code": "scene_source_svg_path_declaration_missing"})
    else:
        try:
            declared_source = resolve_inside_workspace(declared_source_svg, scene_path.parent)
        except (FileNotFoundError, ValueError) as exc:
            issues.append(
                {"code": "scene_source_svg_path_invalid", "value": declared_source_svg, "detail": str(exc)}
            )
        else:
            if declared_source != source_path:
                issues.append(
                    {
                        "code": "scene_source_svg_path_mismatch",
                        "expected": str(source_path),
                        "actual": str(declared_source),
                    }
                )

    by_id = {item.id: item for item in scene.objects}
    expected_texts = {str(item["id"]): item for item in contract["texts"]}
    actual_text_ids = {item.id for item in scene.objects if item.text is not None}
    if actual_text_ids != set(expected_texts):
        issues.append(
            {
                "code": "text_object_inventory_mismatch",
                "missing": sorted(set(expected_texts) - actual_text_ids),
                "unexpected": sorted(actual_text_ids - set(expected_texts)),
            }
        )
    for text_id, expected in expected_texts.items():
        actual = by_id.get(text_id)
        if actual is None:
            continue
        if actual.text != str(expected["text"]):
            issues.append(
                {"code": "text_content_mismatch", "id": text_id, "expected": expected["text"], "actual": actual.text}
            )
        if actual.font_family != str(expected["font_family"]):
            issues.append(
                {
                    "code": "text_font_family_mismatch",
                    "id": text_id,
                    "expected": expected["font_family"],
                    "actual": actual.font_family,
                }
            )
        expected_size = float(expected["font_size_pt"])
        if actual.font_size_pt is None or abs(actual.font_size_pt - expected_size) > 0.01:
            issues.append(
                {
                    "code": "text_font_size_mismatch",
                    "id": text_id,
                    "expected_pt": expected_size,
                    "actual_pt": actual.font_size_pt,
                }
            )

    connectors = [item for item in scene.objects if item.kind == "connector"]
    object_id_set = set(ids)
    for connector in connectors:
        if not connector.source_id or not connector.target_id:
            issues.append({"code": "connector_endpoint_missing", "id": connector.id})
        else:
            for role, endpoint in (("source", connector.source_id), ("target", connector.target_id)):
                if endpoint not in object_id_set or endpoint == connector.id:
                    issues.append(
                        {"code": "connector_endpoint_invalid", "id": connector.id, "role": role, "endpoint": endpoint}
                    )
    expected_connections = {
        (str(item["id"]), str(item["source_id"]), str(item["target_id"]))
        for item in contract.get("connections", [])
    }
    actual_connections = {(item.id, item.source_id, item.target_id) for item in connectors}
    if actual_connections != expected_connections:
        issues.append(
            {
                "code": "connection_topology_mismatch",
                "missing": sorted(expected_connections - actual_connections),
                "unexpected": sorted(actual_connections - expected_connections),
            }
        )

    counts = computed_counts(scene.objects)
    count_mismatches = {
        key: {"expected": expected, "actual": counts[key]}
        for key, expected in contract["object_counts"].items()
        if counts[key] != expected
    }
    if count_mismatches:
        issues.append({"code": "object_count_mismatch", "counts": count_mismatches})

    expected_atoms = {str(item["id"]): item for item in contract.get("atomic_rasters", [])}
    actual_atoms = {item.id: item for item in scene.objects if item.atomic is not None}
    if set(actual_atoms) != set(expected_atoms):
        issues.append(
            {
                "code": "atomic_raster_inventory_mismatch",
                "missing": sorted(set(expected_atoms) - set(actual_atoms)),
                "unexpected": sorted(set(actual_atoms) - set(expected_atoms)),
            }
        )
    atom_summaries = []
    for atom_id, expected in expected_atoms.items():
        actual_object = actual_atoms.get(atom_id)
        if actual_object is None:
            continue
        actual = actual_object.atomic or {}
        expected_hash = str(expected["source_sha256"]).lower()
        source_file = resolve_inside_workspace(str(expected["source_file"]), contract_path.parent)
        source_hash = sha256_file(source_file)
        if source_hash != expected_hash:
            issues.append(
                {"code": "atomic_raster_source_hash_mismatch", "id": atom_id, "expected": expected_hash, "actual": source_hash}
            )
        for key in ("source_file", "source_sha256", "raster_reason"):
            expected_value = expected[key]
            actual_value = actual.get(key)
            if key.endswith("sha256") and actual_value is not None:
                actual_value = str(actual_value).lower()
            if key == "source_file" and actual_value is not None:
                if Path(str(actual_value)).name != Path(str(expected_value)).name:
                    issues.append(
                        {"code": "atomic_raster_metadata_mismatch", "id": atom_id, "field": key, "expected": expected_value, "actual": actual.get(key)}
                    )
            elif actual_value != expected_value:
                issues.append(
                    {"code": "atomic_raster_metadata_mismatch", "id": atom_id, "field": key, "expected": expected_value, "actual": actual.get(key)}
                )
        if actual.get("evidence") is not True:
            issues.append({"code": "atomic_raster_not_marked_evidence", "id": atom_id})
        embedded = decode_data_uri(actual.get("data_uri"))
        embedded_hash = sha256_bytes(embedded) if embedded is not None else actual.get("embedded_sha256")
        if embedded_hash is not None and str(embedded_hash).lower() != expected_hash:
            issues.append(
                {"code": "atomic_raster_embedded_hash_mismatch", "id": atom_id, "expected": expected_hash, "actual": embedded_hash}
            )
        if expected.get("embedded_required", False) and embedded is None:
            issues.append({"code": "atomic_raster_embedded_payload_missing", "id": atom_id})
        atom_summaries.append(
            {"id": atom_id, "source_file": str(source_file), "source_sha256": expected_hash, "embedded_payload_checked": embedded is not None}
        )
    return issues, {
        "counts": counts,
        "canvas_mm": {"width": scene.width_mm, "height": scene.height_mm},
        "source_svg": {"path": str(source_path), "sha256": actual_source_hash},
        "provenance_manifest": provenance_summary,
        "atomic_rasters": atom_summaries,
    }


def audit_runtime(
    scene: ParsedScene,
    scene_path: Path,
    contract: dict,
    contract_path: Path,
    counts: Dict[str, int],
) -> Tuple[bool, List[dict], Optional[dict]]:
    runtime = contract.get("backend_runtime", {})
    status = runtime.get("status", "not-run") if isinstance(runtime, dict) else "not-run"
    evidence_raw = runtime.get("evidence_file") if isinstance(runtime, dict) else None
    issues: List[dict] = []
    if scene.runtime_claim is True and status != "verified":
        issues.append({"code": "backend_runtime_claim_unsubstantiated"})
    if status != "verified" or not evidence_raw:
        issues.append({"code": "backend_runtime_evidence_missing", "status": status})
        return False, issues, None
    evidence_path = resolve_inside_workspace(str(evidence_raw), contract_path.parent)
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    required = {"backend", "scene_sha256", "runtime_version", "opened", "saved", "reopened", "object_counts"}
    if not required.issubset(evidence):
        issues.append({"code": "backend_runtime_evidence_incomplete", "missing": sorted(required - set(evidence))})
        return False, issues, evidence
    if evidence.get("backend") != scene.backend:
        issues.append({"code": "backend_runtime_backend_mismatch"})
    actual_scene_hash = sha256_file(scene_path)
    if str(evidence.get("scene_sha256", "")).lower() != actual_scene_hash:
        issues.append({"code": "backend_runtime_scene_hash_mismatch"})
    for checkpoint in ("opened", "saved", "reopened"):
        if evidence.get(checkpoint) is not True:
            issues.append({"code": "backend_runtime_checkpoint_failed", "checkpoint": checkpoint})
    if not str(evidence.get("runtime_version", "")).strip():
        issues.append({"code": "backend_runtime_version_missing"})
    expected_runtime_counts = {key: counts[key] for key in contract["object_counts"]}
    if evidence.get("object_counts") != expected_runtime_counts:
        issues.append(
            {
                "code": "backend_runtime_object_count_mismatch",
                "expected": expected_runtime_counts,
                "actual": evidence.get("object_counts"),
            }
        )
    return not issues, issues, {"path": str(evidence_path), **evidence}


def audit_backend_scene(scene_path: Path, contract_path: Path) -> dict:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    validate_contract(contract)
    scene = parse_scene(scene_path, contract)
    if scene.backend != contract["backend"]:
        raise ValueError("Parsed backend does not match contract")
    structural_issues, summary = audit_structure(scene, scene_path, contract, contract_path)
    runtime_verified, runtime_issues, runtime_evidence = audit_runtime(
        scene, scene_path, contract, contract_path, summary["counts"]
    )
    structure_pass = not structural_issues
    return {
        "schema_version": "backend-scene-audit-v1",
        "backend": scene.backend,
        "scene": str(scene_path),
        "scene_sha256": sha256_file(scene_path),
        "contract": str(contract_path),
        "structure_pass": structure_pass,
        "backend_runtime_verified": runtime_verified,
        "pass": structure_pass and runtime_verified,
        "structural_issues": structural_issues,
        "runtime_issues": runtime_issues,
        "summary": summary,
        "runtime_evidence": runtime_evidence,
    }


def atomic_write_json(path: Path, payload: dict, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError("Output exists; use a new path or --force: %s" % path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="\n", suffix=".json", dir=str(path.parent), delete=False
    )
    temporary = Path(handle.name)
    try:
        with handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(str(temporary), str(path))
    finally:
        if temporary.exists():
            temporary.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit a Visio SceneGraph JSON or draw.io mxGraph XML scene.")
    parser.add_argument("scene", type=lambda raw: resolve_inside_workspace(raw, Path.cwd()))
    parser.add_argument("--contract", required=True, type=lambda raw: resolve_inside_workspace(raw, Path.cwd()))
    parser.add_argument("--json-out", type=lambda raw: resolve_inside_workspace(raw, Path.cwd(), must_exist=False))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--require-pass", action="store_true")
    args = parser.parse_args()
    result = audit_backend_scene(args.scene, args.contract)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.json_out:
        atomic_write_json(args.json_out, result, args.force)
    if args.require_pass and not result["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
