from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import math
import os
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


SVG_NS = "{http://www.w3.org/2000/svg}"
PT_PER_MM = 72.0 / 25.4
ALLOWED_KINDS = {"surface_plots", "circular_infographic", "detection_matrix"}
ALLOWED_STATUSES = {"prototype", "blocked", "candidate", "approved"}
VECTOR_ICON_TYPES = {"g", "path", "line", "polyline", "polygon", "rect", "ellipse", "circle"}
VECTOR_GEOMETRY_TYPES = VECTOR_ICON_TYPES - {"g"}
ONE_MM_MEANINGS = {
    "stroke_width",
    "tick_length",
    "marker_dimension",
    "scale_bar_length",
    "not_applicable",
    "unresolved",
}


def load_editability_auditor():
    path = Path(__file__).resolve().with_name("audit_editability.py")
    spec = importlib.util.spec_from_file_location("publication_gate_editability_audit", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


EDITABILITY = load_editability_auditor()


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def resolve_inside_workspace(raw: str, base: Path, *, must_exist: bool = True) -> Path:
    workspace = Path.cwd().resolve()
    requested = Path(raw)
    path = (requested if requested.is_absolute() else base / requested).resolve()
    if path != workspace and workspace not in path.parents:
        raise ValueError(f"Path must stay inside workspace: {path}")
    if must_exist and not path.is_file():
        raise FileNotFoundError(path)
    return path


def add_issue(issues: List[Dict[str, Any]], code: str, **details: Any) -> None:
    issues.append({"code": code, **details})


def flatten_recipe_elements(elements: Sequence[dict]) -> List[dict]:
    flattened: List[dict] = []
    for element in elements:
        flattened.append(element)
        if element.get("type") == "group":
            flattened.extend(flatten_recipe_elements(element.get("children", [])))
    return flattened


def validate_gate_spec(spec: dict) -> None:
    required = {
        "candidate_id",
        "kind",
        "recipe",
        "svg",
        "declared_status",
        "illustrator_evidence",
        "manual_visual_review",
        "one_mm_decision",
        "minimum_atomic_rasters",
        "required_atomic_raster_ids",
        "icons_required",
        "required_vector_icon_ids",
        "required_vector_object_ids",
        "font_size_exceptions",
        "documented_blockers",
    }
    missing = sorted(required - set(spec))
    if missing:
        raise ValueError("Publication gate is missing: " + ", ".join(missing))
    if spec["kind"] not in ALLOWED_KINDS:
        raise ValueError("Unsupported publication gate kind")
    if spec["declared_status"] not in ALLOWED_STATUSES:
        raise ValueError("Unsupported declared_status")
    if not isinstance(spec["minimum_atomic_rasters"], int) or spec["minimum_atomic_rasters"] < 0:
        raise ValueError("minimum_atomic_rasters must be a non-negative integer")
    if not isinstance(spec["required_vector_icon_ids"], list):
        raise ValueError("required_vector_icon_ids must be a list")
    if not isinstance(spec["required_atomic_raster_ids"], list):
        raise ValueError("required_atomic_raster_ids must be a list")
    if not isinstance(spec["required_vector_object_ids"], list):
        raise ValueError("required_vector_object_ids must be a list")
    if not isinstance(spec["font_size_exceptions"], list):
        raise ValueError("font_size_exceptions must be a list")
    if not isinstance(spec["documented_blockers"], list):
        raise ValueError("documented_blockers must be a list")
    expected_counts = spec.get("expected_illustrator_counts")
    if expected_counts is not None:
        required_count_keys = {
            "text_frames", "path_items", "raster_items", "placed_items", "warnings"
        }
        if not isinstance(expected_counts, dict) or set(expected_counts) != required_count_keys:
            raise ValueError("expected_illustrator_counts must declare all five exact counts")
        if any(not isinstance(value, int) or value < 0 for value in expected_counts.values()):
            raise ValueError("expected_illustrator_counts values must be non-negative integers")
    decision = spec["one_mm_decision"]
    if decision.get("meaning") not in ONE_MM_MEANINGS:
        raise ValueError("Unsupported one_mm_decision meaning")
    if decision.get("approval_status") not in {"pending", "approved", "rejected"}:
        raise ValueError("Unsupported one_mm_decision approval_status")
    if not isinstance(decision.get("object_ids"), list):
        raise ValueError("one_mm_decision.object_ids must be a list")
    evidence_status = spec["illustrator_evidence"].get("status")
    if evidence_status not in {"required-but-missing", "partial", "available"}:
        raise ValueError("Unsupported illustrator_evidence status")
    if not isinstance(spec["illustrator_evidence"].get("audits"), dict):
        raise ValueError("illustrator_evidence.audits must be an object")
    source_documents = spec["illustrator_evidence"].get("source_documents")
    if source_documents is not None:
        required_stages = {"svg_import", "ai_reopen", "pdf_reopen"}
        if not isinstance(source_documents, dict) or set(source_documents) != required_stages:
            raise ValueError(
                "illustrator_evidence.source_documents must name svg_import, ai_reopen, and pdf_reopen"
            )
    visual_status = spec["manual_visual_review"].get("status")
    if visual_status not in {"pending", "failed", "passed"}:
        raise ValueError("Unsupported manual_visual_review status")


def marker_risks(root: ET.Element) -> List[dict]:
    risks = []
    for element in root.iter():
        if local_name(element.tag) == "marker":
            risks.append({"id": element.attrib.get("id"), "kind": "marker_definition"})
        for key, value in element.attrib.items():
            local_key = key.rsplit("}", 1)[-1]
            if local_key in {"marker-start", "marker-mid", "marker-end"}:
                risks.append(
                    {"id": element.attrib.get("id"), "kind": "marker_attribute", "attribute": local_key}
                )
            if local_key == "style" and re.search(r"marker-(?:start|mid|end)\s*:", value):
                risks.append({"id": element.attrib.get("id"), "kind": "marker_style"})
    return risks


def vector_icon_issues(root: ET.Element, icon_ids: Sequence[str], icons_required: bool) -> List[dict]:
    issues = []
    by_id = {element.attrib.get("id"): element for element in root.iter() if element.attrib.get("id")}
    if icons_required and not icon_ids:
        issues.append({"code": "icon_inventory_missing"})
    for icon_id in icon_ids:
        element = by_id.get(icon_id)
        if element is None:
            issues.append({"code": "required_vector_icon_missing", "id": icon_id})
            continue
        descendants = list(element.iter())
        types = {local_name(item.tag) for item in descendants}
        if "image" in types or "feImage" in types or "foreignObject" in types:
            issues.append({"code": "icon_contains_raster_or_foreign_object", "id": icon_id})
        if "filter" in types or any("filter" in item.attrib for item in descendants):
            issues.append({"code": "icon_requires_raster_effect", "id": icon_id})
        if local_name(element.tag) not in VECTOR_ICON_TYPES or not types.intersection(VECTOR_GEOMETRY_TYPES):
            issues.append({"code": "icon_has_no_vector_geometry", "id": icon_id})
    return issues


def recipe_text_elements(recipe: dict) -> List[dict]:
    return [
        element
        for element in flatten_recipe_elements(recipe.get("elements", []))
        if element.get("type") in {"text", "text_path"}
    ]


def exception_matches(frame: dict, exceptions: Sequence[dict]) -> bool:
    return any(
        frame.get("contents") == item.get("contents")
        and abs(float(frame.get("size_pt", 0)) - float(item.get("size_pt", -1))) <= 0.01
        and str(item.get("reason", "")).strip()
        for item in exceptions
    )


def audit_illustrator(
    spec: dict,
    recipe: dict,
    base: Path,
    expected_atomic_count: int,
    expected_text_count: int,
    issues: List[Dict[str, Any]],
    evidence_summary: Optional[Dict[str, Any]] = None,
) -> Optional[dict]:
    evidence = spec["illustrator_evidence"]
    audit_paths = evidence.get("audits", {})
    expected_sources = evidence.get("source_documents", {})
    required_stages = {"svg_import", "ai_reopen", "pdf_reopen"}
    if evidence["status"] == "required-but-missing" or not audit_paths:
        add_issue(issues, "illustrator_evidence_required_but_missing")
        return None
    if set(audit_paths) != required_stages:
        add_issue(
            issues,
            "illustrator_roundtrip_stages_incomplete",
            available=sorted(audit_paths),
            required=sorted(required_stages),
        )
    if evidence["status"] == "available" and set(audit_paths) != required_stages:
        add_issue(issues, "illustrator_evidence_status_overstated")
    if evidence["status"] == "partial" and set(audit_paths) == required_stages:
        add_issue(issues, "illustrator_evidence_status_understated")
    expected_font = str(recipe.get("contract", {}).get("required_font_family", "Times New Roman"))
    expected_size = float(recipe.get("contract", {}).get("required_font_size_pt", 8.5))
    exceptions = spec["font_size_exceptions"]
    expected_vector_ids = {
        element["id"]
        for element in flatten_recipe_elements(recipe.get("elements", []))
        if element.get("type")
        in {"line", "rect", "ellipse", "polyline", "polygon", "path", "arc", "annular_sector"}
    }
    expected_vector_ids.update(spec["required_vector_object_ids"])
    loaded = {}
    for stage, raw_path in audit_paths.items():
        path = resolve_inside_workspace(raw_path, base)
        audit = json.loads(path.read_text(encoding="utf-8"))
        loaded[stage] = audit
        counts = audit.get("counts", {})
        expected_counts = spec.get("expected_illustrator_counts")
        if expected_counts is not None:
            actual_counts = {
                "text_frames": counts.get("text_frames"),
                "path_items": counts.get("path_items"),
                "raster_items": counts.get("raster_items"),
                "placed_items": counts.get("placed_items"),
                "warnings": len(audit.get("warnings", [])),
            }
            if actual_counts != expected_counts:
                add_issue(
                    issues,
                    "illustrator_object_count_mismatch",
                    stage=stage,
                    expected=expected_counts,
                    actual=actual_counts,
                )
        if evidence_summary is not None:
            evidence_summary.setdefault("illustrator", {})[stage] = {
                "audit": str(path),
                "source_document": audit.get("source_document"),
                "text_frames": counts.get("text_frames"),
                "path_items": counts.get("path_items"),
                "raster_items": counts.get("raster_items"),
                "placed_items": counts.get("placed_items"),
                "warnings": len(audit.get("warnings", [])),
            }
        expected_source_raw = expected_sources.get(stage)
        if expected_source_raw:
            expected_source = resolve_inside_workspace(expected_source_raw, base)
            if stage == "svg_import":
                gate_svg = resolve_inside_workspace(spec["svg"], base)
                if expected_source != gate_svg:
                    add_issue(
                        issues,
                        "illustrator_svg_source_not_gate_svg",
                        expected=str(gate_svg),
                        declared=str(expected_source),
                    )
            recorded_source_raw = audit.get("source_document")
            if not recorded_source_raw:
                add_issue(issues, "illustrator_source_document_missing", stage=stage)
            else:
                try:
                    recorded_source = resolve_inside_workspace(str(recorded_source_raw), path.parent)
                except (FileNotFoundError, ValueError) as exc:
                    add_issue(
                        issues,
                        "illustrator_source_document_invalid",
                        stage=stage,
                        value=str(recorded_source_raw),
                        detail=str(exc),
                    )
                else:
                    if recorded_source != expected_source:
                        add_issue(
                            issues,
                            "illustrator_source_document_mismatch",
                            stage=stage,
                            expected=str(expected_source),
                            actual=str(recorded_source),
                        )
        if counts.get("placed_items", 0) or (
            spec["kind"] == "circular_infographic" and counts.get("raster_items", 0)
        ):
            add_issue(
                issues,
                "illustrator_unexpected_raster_or_placed_item",
                stage=stage,
                placed_items=counts.get("placed_items"),
                raster_items=counts.get("raster_items"),
            )
        actual_raster_count = int(counts.get("placed_items", 0)) + int(counts.get("raster_items", 0))
        if expected_atomic_count and actual_raster_count != expected_atomic_count:
            add_issue(
                issues,
                "illustrator_atomic_raster_count_mismatch",
                stage=stage,
                actual=actual_raster_count,
                expected=expected_atomic_count,
            )
        actual_vector_ids = {
            item.get("name") for item in audit.get("path_items", []) if item.get("name")
        }
        for missing_id in sorted(expected_vector_ids - actual_vector_ids):
            add_issue(
                issues,
                "illustrator_vector_object_missing",
                stage=stage,
                id=missing_id,
            )
        for frame in audit.get("text_frames", []):
            font = str(frame.get("font_postscript_name", ""))
            if expected_font == "Times New Roman" and "TimesNewRoman" not in font.replace(" ", ""):
                add_issue(
                    issues,
                    "illustrator_font_mismatch",
                    stage=stage,
                    frame=frame.get("name"),
                    value=font,
                )
            size = float(frame.get("size_pt", 0))
            if abs(size - expected_size) > 0.01 and not exception_matches(frame, exceptions):
                add_issue(
                    issues,
                    "illustrator_font_size_mismatch",
                    stage=stage,
                    frame=frame.get("name"),
                    contents=frame.get("contents"),
                    value_pt=size,
                )
            if frame.get("hidden") or frame.get("locked"):
                add_issue(
                    issues,
                    "illustrator_text_not_directly_editable",
                    stage=stage,
                    frame=frame.get("name"),
                )
        if counts.get("text_frames", 0) < expected_text_count:
            add_issue(
                issues,
                "illustrator_text_frame_count_too_low",
                stage=stage,
                actual=counts.get("text_frames", 0),
                expected_minimum=expected_text_count,
            )
    pdf_audit_raw = evidence.get("pdf_audit")
    if pdf_audit_raw:
        pdf_audit_path = resolve_inside_workspace(pdf_audit_raw, base)
        pdf_audit = json.loads(pdf_audit_path.read_text(encoding="utf-8"))
        if evidence_summary is not None:
            evidence_summary["pdf"] = {
                "audit": str(pdf_audit_path),
                "file": pdf_audit.get("file"),
                "pass": pdf_audit.get("pass"),
                "page_count": pdf_audit.get("page_count"),
                "font_resources": pdf_audit.get("font_resources", []),
            }
        if pdf_audit.get("pass") is not True:
            add_issue(
                issues,
                "pdf_structural_audit_failed",
                failures=pdf_audit.get("failures", []),
            )
        text_expectations = evidence.get("pdf_text_expectations", {})
        extracted_text = str(pdf_audit.get("extracted_text", ""))
        for required_text in text_expectations.get("required_extractable_text", []):
            if required_text not in extracted_text:
                add_issue(
                    issues,
                    "pdf_required_text_not_extractable",
                    text=required_text,
                )
        font_resources = [str(value) for value in pdf_audit.get("font_resources", [])]
        for fragment in text_expectations.get("forbidden_font_name_fragments", []):
            matches = [value for value in font_resources if fragment in value]
            if matches:
                add_issue(
                    issues,
                    "pdf_forbidden_font_resource",
                    fragment=fragment,
                    matches=matches,
                )
        expected_pdf_raw = expected_sources.get("pdf_reopen")
        recorded_pdf_raw = pdf_audit.get("file")
        if expected_pdf_raw and recorded_pdf_raw:
            expected_pdf = resolve_inside_workspace(expected_pdf_raw, base)
            try:
                recorded_pdf = resolve_inside_workspace(str(recorded_pdf_raw), pdf_audit_path.parent)
            except (FileNotFoundError, ValueError) as exc:
                add_issue(
                    issues,
                    "pdf_structural_audit_source_invalid",
                    value=str(recorded_pdf_raw),
                    detail=str(exc),
                )
            else:
                if recorded_pdf != expected_pdf:
                    add_issue(
                        issues,
                        "pdf_structural_audit_source_mismatch",
                        expected=str(expected_pdf),
                        actual=str(recorded_pdf),
                    )
        elif expected_pdf_raw:
            add_issue(issues, "pdf_structural_audit_source_missing")
    return loaded.get("ai_reopen") or loaded.get("pdf_reopen") or loaded.get("svg_import")


def audit_text_paths(
    spec: dict,
    recipe: dict,
    illustrator_audit: Optional[dict],
    base: Path,
    issues: List[Dict[str, Any]],
) -> None:
    expected = [element for element in recipe_text_elements(recipe) if element.get("type") == "text_path"]
    if not expected:
        return
    raw = spec["illustrator_evidence"].get("text_path_audit")
    if not raw:
        add_issue(issues, "illustrator_text_path_audit_missing")
        return
    payload = json.loads(resolve_inside_workspace(raw, base).read_text(encoding="utf-8"))
    if not payload.get("pass"):
        add_issue(issues, "illustrator_text_path_audit_failed", findings=payload.get("issues", []))
    actual_ids = {item.get("id") for item in payload.get("text_path_results", [])}
    if payload.get("expected_text_path_count") != len(expected):
        add_issue(
            issues,
            "illustrator_text_path_count_mismatch",
            actual=payload.get("expected_text_path_count"),
            expected=len(expected),
        )
    if illustrator_audit is not None:
        recorded_source = str(payload.get("source_audit", "")).replace("/", "\\").lower()
        illustrator_source = str(illustrator_audit.get("source_document", "")).replace("/", "\\").lower()
        if recorded_source and illustrator_source and recorded_source != illustrator_source:
            add_issue(issues, "illustrator_text_path_audit_source_mismatch")
    for element in expected:
        if element["id"] not in actual_ids:
            add_issue(issues, "illustrator_text_path_result_missing", id=element["id"])
    if illustrator_audit is not None:
        frames = {frame.get("name"): frame for frame in illustrator_audit.get("text_frames", [])}
        for element in expected:
            frame = frames.get(element["id"])
            if frame is None or frame.get("kind") != "path" or not frame.get("text_path"):
                add_issue(issues, "illustrator_native_path_text_missing", id=element["id"])


def physical_geometry_mm(element: dict, meaning: str, axis: Optional[str], mm_per_px: float) -> Optional[float]:
    kind = element.get("type")
    if meaning in {"tick_length", "scale_bar_length"} and kind == "line":
        return math.hypot(
            float(element["x2_px"]) - float(element["x1_px"]),
            float(element["y2_px"]) - float(element["y1_px"]),
        ) * mm_per_px
    if meaning == "marker_dimension":
        if axis not in {"width", "height", "diameter"}:
            return None
        if axis == "diameter" and element.get("diameter_mm") is not None:
            return float(element["diameter_mm"])
        if kind == "ellipse":
            width = 2 * float(element["rx_px"]) * mm_per_px
            height = 2 * float(element["ry_px"]) * mm_per_px
        elif kind == "rect":
            width = float(element["width_px"]) * mm_per_px
            height = float(element["height_px"]) * mm_per_px
        else:
            return None
        return max(width, height) if axis == "diameter" else (width if axis == "width" else height)
    return None


def audit_one_mm(
    spec: dict,
    recipe: dict,
    illustrator_audit: Optional[dict],
    issues: List[Dict[str, Any]],
) -> None:
    decision = spec["one_mm_decision"]
    meaning = decision["meaning"]
    if meaning == "not_applicable":
        if spec["kind"] == "surface_plots":
            add_issue(issues, "one_mm_not_applicable_invalid_for_surface")
        return
    if meaning == "unresolved" or decision["approval_status"] != "approved":
        add_issue(
            issues,
            "one_mm_semantics_unresolved_or_unapproved",
            meaning=meaning,
            approval_status=decision["approval_status"],
        )
        return
    object_ids = decision["object_ids"]
    if not object_ids:
        add_issue(issues, "one_mm_object_inventory_missing")
        return
    elements = {element["id"]: element for element in flatten_recipe_elements(recipe.get("elements", []))}
    defaults = recipe.get("defaults", {})
    mm_per_px = float(recipe["canvas"]["print_width_mm"]) / float(recipe["canvas"]["width_px"])
    illustrator_paths = {
        item.get("name"): item for item in (illustrator_audit or {}).get("path_items", [])
    }
    for object_id in object_ids:
        element = elements.get(object_id)
        if element is None:
            add_issue(issues, "one_mm_object_missing", id=object_id)
            continue
        if meaning == "stroke_width":
            stroke_mm = float(element.get("stroke_width_mm", defaults.get("stroke_width_mm", 0)))
            if abs(stroke_mm - 1.0) > 0.001:
                add_issue(issues, "one_mm_stroke_recipe_mismatch", id=object_id, value_mm=stroke_mm)
            ai_path = illustrator_paths.get(object_id)
            if illustrator_audit is None:
                continue
            if ai_path is None or abs(float(ai_path.get("stroke_width_pt", 0)) - PT_PER_MM) > 0.01:
                add_issue(issues, "one_mm_stroke_illustrator_mismatch", id=object_id)
        else:
            value = physical_geometry_mm(
                element, meaning, decision.get("dimension_axis"), mm_per_px
            )
            if value is None:
                add_issue(issues, "one_mm_geometry_not_measurable", id=object_id, meaning=meaning)
            elif abs(value - 1.0) > 0.01:
                add_issue(issues, "one_mm_geometry_mismatch", id=object_id, value_mm=value)


def audit_gate(spec_path: Path) -> dict:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    validate_gate_spec(spec)
    base = spec_path.parent
    recipe_path = resolve_inside_workspace(spec["recipe"], base)
    svg_path = resolve_inside_workspace(spec["svg"], base)
    recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
    root = ET.parse(svg_path).getroot()
    issues: List[Dict[str, Any]] = []

    if recipe.get("elements") is not None:
        editability_contract = EDITABILITY.contract_from_recipe(recipe)
    else:
        declared = recipe.get("contract", {})
        defaults = recipe.get("defaults", {})
        editability_contract = EDITABILITY.SvgAuditContract(
            font_family=str(declared.get("required_font_family", defaults.get("font_family", "Times New Roman"))),
            font_size_pt=float(declared.get("required_font_size_pt", defaults.get("font_size_pt", 8.5))),
            expected_width_mm=float(recipe["canvas"]["print_width_mm"]),
        )
    editability_result = EDITABILITY.audit_svg(svg_path, editability_contract)
    editability_failures = list(editability_result["failures"])
    physical_font_contract = recipe.get("font_size_contract", {})
    declared_user_units = physical_font_contract.get("svg_user_units")
    if declared_user_units is not None and "font_size_mismatch" in editability_failures:
        expected_user_units = float(declared_user_units)
        actual_values = []
        for text in root.iter(f"{SVG_NS}text"):
            raw_value = EDITABILITY.style_value(text, "font-size")
            match = re.fullmatch(r"\s*([0-9.]+)\s*", raw_value or "")
            actual_values.append(float(match.group(1)) if match else None)
        if actual_values and all(
            value is not None and abs(value - expected_user_units) <= 1e-9
            for value in actual_values
        ):
            editability_failures.remove("font_size_mismatch")
    if editability_failures:
        add_issue(issues, "svg_editability_audit_failed", failures=editability_failures)
    if editability_result.get("annotation_occlusion_issues"):
        add_issue(
            issues,
            "annotation_occlusion_contract_failed",
            findings=editability_result["annotation_occlusion_issues"],
        )

    risks = marker_risks(root)
    if risks:
        add_issue(issues, "svg_marker_import_risk", findings=risks)

    atomic_records = list(recipe.get("atomic_rasters", []))
    manifest = None
    manifest_raw = spec.get("atomic_manifest") or recipe.get("atomic_manifest")
    if manifest_raw:
        manifest_base = base if spec.get("atomic_manifest") else recipe_path.parent
        manifest = json.loads(resolve_inside_workspace(manifest_raw, manifest_base).read_text(encoding="utf-8"))
        if not atomic_records:
            atomic_records = list(manifest.get("panels", []))
    atomic_count = len(atomic_records)
    required_atomic = int(spec["minimum_atomic_rasters"])
    if atomic_count < required_atomic:
        add_issue(
            issues,
            "scientific_atomic_raster_count_too_low",
            actual=atomic_count,
            expected_minimum=required_atomic,
        )
    if spec["kind"] == "detection_matrix":
        if not recipe.get("contract", {}).get("require_atomic_rasters"):
            add_issue(issues, "detection_matrix_atomic_raster_contract_missing")
        images_by_id = {
            element.attrib.get("id"): element
            for element in root.iter(f"{SVG_NS}image")
            if element.attrib.get("id")
        }
        baked_annotation_ids = []
        required_metadata = {
            "id", "source_file", "source_sha256", "embedded_sha256",
            "byte_identical", "evidence", "raster_reason",
        }
        for record in atomic_records:
            record_id = record.get("id")
            missing_metadata = sorted(required_metadata - set(record))
            if missing_metadata:
                add_issue(
                    issues,
                    "detection_atom_metadata_incomplete",
                    id=record_id,
                    missing=missing_metadata,
                )
                continue
            source_hash = str(record["source_sha256"]).lower()
            embedded_hash = str(record["embedded_sha256"]).lower()
            if (
                record.get("evidence") is not True
                or record.get("byte_identical") is not True
                or source_hash != embedded_hash
            ):
                add_issue(issues, "detection_atom_evidence_contract_failed", id=record_id)
            image = images_by_id.get(record_id)
            if image is None:
                add_issue(issues, "detection_atom_missing_from_svg", id=record_id)
            else:
                if image.attrib.get("data-source-sha256", "").lower() != source_hash:
                    add_issue(issues, "detection_atom_svg_hash_metadata_mismatch", id=record_id)
                if image.attrib.get("data-evidence") != "true" or image.attrib.get(
                    "data-atomic-raster-unit"
                ) != "true":
                    add_issue(issues, "detection_atom_svg_evidence_metadata_missing", id=record_id)
                href = image.attrib.get("{http://www.w3.org/1999/xlink}href") or image.attrib.get(
                    "href", ""
                )
                if not href.startswith("data:image/png;base64,"):
                    add_issue(issues, "detection_atom_not_embedded_png", id=record_id)
                else:
                    try:
                        payload = base64.b64decode(href.split(",", 1)[1], validate=True)
                    except ValueError:
                        add_issue(issues, "detection_atom_invalid_base64", id=record_id)
                    else:
                        if hashlib.sha256(payload).hexdigest() != embedded_hash:
                            add_issue(issues, "detection_atom_embedded_hash_mismatch", id=record_id)
            reason = str(record.get("raster_reason", "")).lower()
            if "baked" in reason and ("detection" in reason or "annotation" in reason):
                baked_annotation_ids.append(record_id)
        if baked_annotation_ids:
            add_issue(
                issues,
                "detection_annotations_baked_in_atomic_rasters",
                atomic_ids=baked_annotation_ids,
            )
    if spec["kind"] == "surface_plots":
        contract = recipe.get("contract", {})
        if not (
            contract.get("require_atomic_rasters")
            or contract.get("require_three_atomic_panel_rasters")
        ):
            add_issue(issues, "surface_atomic_raster_contract_not_required")
        if recipe.get("masks"):
            add_issue(issues, "surface_legacy_raster_masks_present", count=len(recipe["masks"]))
        if manifest is not None:
            pending = [
                panel.get("id")
                for panel in manifest.get("panels", [])
                if "pending" in str(panel.get("status", "")).lower()
            ]
            if pending:
                add_issue(
                    issues,
                    "surface_annotation_occlusion_approval_pending",
                    atomic_ids=pending,
                )
    if spec["kind"] == "circular_infographic":
        if not recipe.get("contract", {}).get("require_zero_rasters"):
            add_issue(issues, "circular_zero_raster_contract_missing")
        if list(root.iter(f"{SVG_NS}image")) or list(root.iter(f"{SVG_NS}feImage")):
            add_issue(issues, "circular_raster_present")

    issues.extend(
        vector_icon_issues(
            root, spec["required_vector_icon_ids"], bool(spec["icons_required"])
        )
    )
    by_id = {element.attrib.get("id"): element for element in root.iter() if element.attrib.get("id")}
    svg_images = list(root.iter(f"{SVG_NS}image"))
    actual_image_ids = {image.attrib["id"] for image in svg_images if image.attrib.get("id")}
    anonymous_images = [image for image in svg_images if not image.attrib.get("id")]
    required_atomic_ids = set(spec["required_atomic_raster_ids"])
    if anonymous_images:
        add_issue(issues, "anonymous_svg_raster", count=len(anonymous_images))
    for missing_id in sorted(required_atomic_ids - actual_image_ids):
        add_issue(issues, "required_atomic_raster_missing_from_svg", id=missing_id)
    for unexpected_id in sorted(actual_image_ids - required_atomic_ids):
        if required_atomic_ids:
            add_issue(issues, "undeclared_svg_raster", id=unexpected_id)
    for image_id in sorted(required_atomic_ids & actual_image_ids):
        image = by_id[image_id]
        if image.attrib.get("data-evidence") != "true":
            add_issue(issues, "atomic_raster_not_marked_evidence", id=image_id)
        if image.attrib.get("data-atomic-raster-unit") != "true":
            add_issue(issues, "atomic_raster_not_marked_atomic", id=image_id)
    for object_id in spec["required_vector_object_ids"]:
        element = by_id.get(object_id)
        if element is None:
            add_issue(issues, "required_vector_object_missing_from_svg", id=object_id)
        elif local_name(element.tag) in {"image", "feImage", "foreignObject"}:
            add_issue(issues, "required_vector_object_is_raster", id=object_id)
    expected_text_count = len(recipe_text_elements(recipe))
    if not expected_text_count:
        expected_text_count = len(list(root.iter(f"{SVG_NS}text")))
    evidence_summary: Dict[str, Any] = {}
    illustrator_audit = audit_illustrator(
        spec,
        recipe,
        base,
        atomic_count,
        expected_text_count,
        issues,
        evidence_summary,
    )
    audit_text_paths(spec, recipe, illustrator_audit, base, issues)
    audit_one_mm(spec, recipe, illustrator_audit, issues)

    visual = spec["manual_visual_review"]
    if visual["status"] != "passed":
        add_issue(issues, "manual_visual_review_not_passed", status=visual["status"])
    elif not visual.get("report"):
        add_issue(issues, "manual_visual_review_report_missing")
    else:
        resolve_inside_workspace(visual["report"], base)

    declared_status = spec["declared_status"]
    documented = [str(value) for value in spec["documented_blockers"] if str(value).strip()]
    status_consistency_issues = []
    if declared_status == "approved" and issues:
        status_consistency_issues.append("approved_candidate_has_blockers")
    if declared_status in {"prototype", "blocked"} and not documented:
        status_consistency_issues.append("blocked_status_has_no_documented_blockers")
    if declared_status == "approved" and documented:
        status_consistency_issues.append("approved_status_still_documents_blockers")
    if declared_status in {"prototype", "blocked"} and not issues:
        status_consistency_issues.append("blocked_status_has_no_detected_blocker")

    return {
        "candidate_id": spec["candidate_id"],
        "kind": spec["kind"],
        "declared_status": declared_status,
        "status_consistent": not status_consistency_issues,
        "publication_ready": declared_status == "approved" and not issues,
        "blockers": issues,
        "documented_blockers": documented,
        "status_consistency_issues": status_consistency_issues,
        "svg_editability_pass": not editability_failures,
        "evidence_summary": evidence_summary,
        "counts": {
            "atomic_rasters": atomic_count,
            "svg_images": len(svg_images),
            "svg_text": len(list(root.iter(f"{SVG_NS}text"))),
        },
    }


def atomic_write_json(path: Path, payload: dict, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"Output exists; use a new path or --force: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="\n", suffix=".json", dir=path.parent, delete=False
    )
    temporary = Path(handle.name)
    try:
        with handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit complex figure publication gate evidence.")
    parser.add_argument("gate_spec", type=lambda raw: resolve_inside_workspace(raw, Path.cwd()))
    parser.add_argument("--json-out", type=lambda raw: resolve_inside_workspace(raw, Path.cwd(), must_exist=False))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args()
    result = audit_gate(args.gate_spec)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.json_out:
        atomic_write_json(args.json_out, result, args.force)
    if not result["status_consistent"] or (args.require_ready and not result["publication_ready"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
