from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

from PIL import Image


PLAN_SCHEMA = "safe-text-cleanup-v1"
AUDIT_SCHEMA = "safe-text-cleanup-audit-v1"


def fail(message: str) -> None:
    raise ValueError(message)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def resolve_inside_workspace(value: Any, base: Path, workspace: Path, must_exist: bool = True) -> Path:
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


def finite_number(value: Any, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        fail("%s must be numeric" % name)
    if not math.isfinite(number):
        fail("%s must be finite" % name)
    return number


def xml_attr(value: Any) -> str:
    return html.escape(str(value), quote=True)


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


def build_overlay(
    plan_path: Path,
    output_svg: Path,
    workspace: Path,
    force: bool = False,
) -> Dict[str, Any]:
    workspace = workspace.resolve()
    plan_path = resolve_inside_workspace(plan_path, Path.cwd(), workspace)
    output_svg = resolve_inside_workspace(output_svg, Path.cwd(), workspace, must_exist=False)
    if output_svg.suffix.lower() != ".svg":
        fail("output must be SVG")
    if output_svg == plan_path:
        fail("output must not overwrite the plan")
    if output_svg.exists() and not force:
        raise FileExistsError("Refusing to overwrite: %s" % output_svg)

    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if plan.get("schema_version") != PLAN_SCHEMA:
        fail("plan schema_version must be %s" % PLAN_SCHEMA)
    if plan.get("scientific_evidence") is not False or plan.get("approval_status") != "approved":
        fail("plan must be approved non-scientific-evidence cleanup")
    replacements = plan.get("replacement_texts")
    regions = plan.get("regions")
    if not isinstance(replacements, list) or not replacements:
        fail("plan must contain replacement_texts")
    if not isinstance(regions, list) or not regions:
        fail("plan must contain cleanup regions")
    region_ids = {str(item.get("id", "")) for item in regions}
    if "" in region_ids or len(region_ids) != len(regions):
        fail("cleanup region ids must be unique")

    base = plan_path.parent
    source_path = resolve_inside_workspace(plan.get("source_image"), base, workspace)
    source_hash = sha256_file(source_path)
    if plan.get("source_sha256") != source_hash:
        fail("plan source_sha256 does not match source image")
    cleaned_path = resolve_inside_workspace(plan.get("output_image"), base, workspace)
    executor_audit_path = resolve_inside_workspace(plan.get("audit_output"), base, workspace)
    executor = json.loads(executor_audit_path.read_text(encoding="utf-8"))
    if executor.get("schema_version") != AUDIT_SCHEMA:
        fail("executor audit schema_version must be %s" % AUDIT_SCHEMA)
    if executor.get("plan_sha256") != sha256_file(plan_path):
        fail("executor audit is stale for the current plan")
    if executor.get("output_sha256") != sha256_file(cleaned_path):
        fail("executor audit output hash does not match cleaned image")
    if executor.get("changed_pixels_outside_mask") != 0 or executor.get("outside_mask_pixel_identity") is not True:
        fail("executor audit does not prove outside-mask pixel identity")
    if executor.get("publication_ready") is not False:
        fail("executor audit must remain publication_ready=false")

    with Image.open(str(cleaned_path)) as opened:
        width_px, height_px = opened.size
        image_format = str(opened.format or "PNG").upper()
    if image_format != "PNG":
        fail("cleaned overlay image must be PNG")
    print_width_mm = finite_number(plan.get("print_width_mm"), "print_width_mm")
    if print_width_mm <= 0 or print_width_mm > 1000:
        fail("print_width_mm must be in (0, 1000]")
    print_height_mm = print_width_mm * height_px / float(width_px)
    user_unit_to_pt = (print_width_mm * 72.0 / 25.4) / float(width_px)
    font_size_user_units = 8.5 / user_unit_to_pt

    text_ids = set()
    text_lines = []
    for index, replacement in enumerate(replacements):
        if not isinstance(replacement, dict):
            fail("replacement_texts[%d] must be an object" % index)
        identifier = str(replacement.get("id", "")).strip()
        text = str(replacement.get("text", "")).strip()
        region_id = str(replacement.get("region_id", "")).strip()
        if not identifier or identifier in text_ids or not text:
            fail("replacement text ids must be unique and text must be non-empty")
        if region_id not in region_ids:
            fail("replacement text references unknown cleanup region")
        if replacement.get("font_family") != "Times New Roman":
            fail("replacement font_family must be Times New Roman")
        size_pt = finite_number(replacement.get("font_size_pt"), "font_size_pt")
        if not math.isclose(size_pt, 8.5, abs_tol=1e-9):
            fail("replacement font_size_pt must be exactly 8.5")
        x = finite_number(replacement.get("x_px"), "x_px")
        y = finite_number(replacement.get("y_px"), "y_px")
        if x < 0 or x > width_px or y < 0 or y > height_px:
            fail("replacement text anchor is outside the canvas")
        anchor = str(replacement.get("text_anchor", "start"))
        if anchor not in {"start", "middle", "end"}:
            fail("text_anchor must be start, middle, or end")
        weight = str(replacement.get("font_weight", "normal"))
        if weight not in {"normal", "bold"}:
            fail("font_weight must be normal or bold")
        fill = str(replacement.get("fill", "#111111"))
        if len(fill) != 7 or not fill.startswith("#"):
            fail("fill must be #RRGGBB")
        try:
            int(fill[1:], 16)
        except ValueError:
            fail("fill must be #RRGGBB")
        rotation = finite_number(replacement.get("rotation_deg", 0.0), "rotation_deg")
        transform = ""
        if not math.isclose(rotation, 0.0, abs_tol=1e-9):
            transform = ' transform="rotate(%s %s %s)"' % (
                xml_attr("%.6g" % rotation), xml_attr("%.6g" % x), xml_attr("%.6g" % y)
            )
        text_lines.append(
            '    <text id="%s" x="%.6g" y="%.6g" text-anchor="%s" '
            'font-family="Times New Roman" font-size="%.10g" '
            'data-declared-font-size-pt="8.5" data-user-unit-to-pt="%.12g" '
            'font-weight="%s" fill="%s" '
            'data-region-id="%s" data-original-text="%s" data-translation-status="%s"%s>%s</text>'
            % (
                xml_attr(identifier), x, y, xml_attr(anchor), font_size_user_units,
                user_unit_to_pt, xml_attr(weight), xml_attr(fill),
                xml_attr(region_id), xml_attr(replacement.get("original_text", "")),
                xml_attr(replacement.get("translation_status", "unspecified")), transform,
                html.escape(text),
            )
        )
        text_ids.add(identifier)

    cleaned_payload = cleaned_path.read_bytes()
    cleaned_hash = hashlib.sha256(cleaned_payload).hexdigest()
    embedded = base64.b64encode(cleaned_payload).decode("ascii")
    svg = "\n".join([
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"',
        '     width="%.6gmm" height="%.6gmm" viewBox="0 0 %d %d"' % (
            print_width_mm, print_height_mm, width_px, height_px
        ),
        '     data-publication-ready="false" data-manual-review-required="true"',
        '     data-physical-font-scaling="viewBox-to-mm">',
        '  <title>Reviewed OCR cleanup with editable Times New Roman text</title>',
        '  <g id="raster-base" data-layer-role="lossless-cleaned-non-evidence-raster">',
        '    <image id="cleaned-raster" x="0" y="0" width="%d" height="%d"' % (width_px, height_px),
        '           data-atomic-raster-unit="true" data-evidence="true"',
        '           data-source-file="%s" data-source-sha256="%s"' % (
            xml_attr(os.path.relpath(str(source_path), str(output_svg.parent)).replace("\\", "/")), source_hash
        ),
        '           data-cleaned-file="%s" data-cleaned-sha256="%s"' % (
            xml_attr(os.path.relpath(str(cleaned_path), str(output_svg.parent)).replace("\\", "/")), cleaned_hash
        ),
        '           data-cleanup-plan-sha256="%s" data-executor-audit-sha256="%s"' % (
            sha256_file(plan_path), sha256_file(executor_audit_path)
        ),
        '           href="data:image/png;base64,%s"' % embedded,
        '           xlink:href="data:image/png;base64,%s"/>' % embedded,
        '  </g>',
        '  <g id="live-text" data-layer-role="editable-annotation">',
        *text_lines,
        '  </g>',
        '</svg>',
        '',
    ])
    atomic_write(output_svg, svg.encode("utf-8"))
    return {
        "schema_version": "cleaned-text-overlay-build-v1",
        "output_svg": str(output_svg),
        "output_svg_sha256": sha256_file(output_svg),
        "source_image": str(source_path),
        "source_image_sha256": source_hash,
        "cleaned_image": str(cleaned_path),
        "cleaned_image_sha256": cleaned_hash,
        "text_count": len(text_lines),
        "font_family": "Times New Roman",
        "font_size_pt": 8.5,
        "print_width_mm": print_width_mm,
        "print_height_mm": print_height_mm,
        "publication_ready": False,
        "manual_review_required": True,
    }


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Embed a safely cleaned raster and add reviewed live Times New Roman 8.5 pt replacements.")
    parser.add_argument("cleanup_plan", type=Path)
    parser.add_argument("output_svg", type=Path)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--force", action="store_true")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    result = build_overlay(args.cleanup_plan, args.output_svg, args.workspace, force=args.force)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
