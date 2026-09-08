from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import math
import os
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


SVG_NS = "{http://www.w3.org/2000/svg}"
PT_PER_MM = 72.0 / 25.4
CSS_PX_PER_MM = 96.0 / 25.4
PATH_NUMBER = r"[+-]?(?:(?:\d+\.\d*)|(?:\.\d+)|(?:\d+))(?:[eE][+-]?\d+)?"
PATH_TOKEN = re.compile(rf"[MmZzLlHhVvCcSsQqTtAa]|{PATH_NUMBER}")
PATH_PARAMETER_COUNTS = {
    "M": 2,
    "L": 2,
    "H": 1,
    "V": 1,
    "C": 6,
    "S": 4,
    "Q": 4,
    "T": 2,
    "A": 7,
}


@dataclass(frozen=True)
class SvgAuditContract:
    font_family: str = "Times New Roman"
    font_size_pt: float = 8.5
    expected_text_count: int | None = None
    stroke_id_prefix: str | None = None
    required_stroke_mm: float | None = None
    required_ids: tuple[str, ...] = ()
    expected_width_mm: float | None = None
    expected_text: tuple[tuple[str, str], ...] = ()
    required_subscripts: tuple[str, ...] = ()
    stroke_expectations: tuple[tuple[str, float], ...] = ()
    require_atomic_rasters: bool = False
    require_no_raster: bool = False
    enforce_declared_atomic_rasters: bool = False
    atomic_rasters: tuple["AtomicRasterExpectation", ...] = ()
    annotation_occlusions: tuple["AnnotationOcclusionExpectation", ...] = ()
    required_element_types: tuple[tuple[str, str], ...] = ()
    required_parent_ids: tuple[tuple[str, str], ...] = ()
    required_gradient_ids: tuple[str, ...] = ()
    require_user_space_gradients: bool = False
    expected_fill_gradients: tuple[tuple[str, str], ...] = ()
    required_text_path_ids: tuple[str, ...] = ()
    expected_text_path_curves: tuple[tuple[str, str], ...] = ()
    arcs: tuple["ArcExpectation", ...] = ()
    annular_sectors: tuple["AnnularSectorExpectation", ...] = ()


@dataclass(frozen=True)
class AtomicRasterExpectation:
    element_id: str
    source_file: str | None
    cleaned_file: str | None
    source_bbox_px: tuple[float, float, float, float]
    canvas_bbox_px: tuple[float, float, float, float]
    canvas_bbox_user: tuple[float, float, float, float]
    evidence: bool


@dataclass(frozen=True)
class AnnotationOcclusionExpectation:
    element_id: str
    atomic_raster_id: str
    source_rect_px: tuple[float, float, float, float]
    canvas_rect_user: tuple[float, float, float, float]
    mode: str
    fill: str
    max_area_fraction: float
    evidence_change_contract: str
    source_crop_sha256: str
    old_annotation_risk: str
    approval_status: str
    approved_by: str
    approval_note: str
    replacement_element_ids: tuple[str, ...]


@dataclass(frozen=True)
class ArcExpectation:
    element_id: str
    cx: float
    cy: float
    radius: float
    start_angle_deg: float
    end_angle_deg: float
    clockwise: bool = True
    tolerance: float = 0.01


@dataclass(frozen=True)
class AnnularSectorExpectation:
    element_id: str
    cx: float
    cy: float
    inner_radius: float
    outer_radius: float
    start_angle_deg: float
    end_angle_deg: float
    clockwise: bool = True
    tolerance: float = 0.01


def workspace_path(raw: str, *, must_exist: bool = False) -> Path:
    workspace = Path.cwd().resolve()
    path = Path(raw)
    path = (path if path.is_absolute() else workspace / path).resolve()
    if path != workspace and workspace not in path.parents:
        raise ValueError(f"Path must stay inside workspace: {path}")
    if must_exist and not path.exists():
        raise FileNotFoundError(path)
    return path


def style_value(element: ET.Element, key: str) -> str | None:
    if key in element.attrib:
        return element.attrib[key]
    style = element.attrib.get("style", "")
    for item in style.split(";"):
        if ":" in item:
            name, value = item.split(":", 1)
            if name.strip() == key:
                return value.strip().strip("'\"")
    return None


def font_size_pt(value: str | None, user_unit_to_pt: float | None = None) -> float | None:
    if not value:
        return None
    match = re.fullmatch(r"\s*([0-9.]+)\s*(pt|px)?\s*", value)
    if not match:
        return None
    number = float(match.group(1))
    unit = match.group(2) or ""
    if user_unit_to_pt is not None and unit in {"", "px"}:
        return number * user_unit_to_pt
    return number if unit == "pt" else number * 0.75


def length_pt(value: str | None) -> float | None:
    if not value:
        return None
    match = re.fullmatch(r"\s*([0-9.]+)\s*(pt|mm|px)?\s*", value)
    if not match:
        return None
    number = float(match.group(1))
    unit = match.group(2) or "px"
    if unit == "pt":
        return number
    if unit == "mm":
        return number * PT_PER_MM
    return number * 0.75


def numeric_attribute(value: str | None) -> float | None:
    if value is None:
        return None
    match = re.fullmatch(r"\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*", value)
    return float(match.group(1)) if match else None


def metadata_bbox(value: str | None) -> tuple[float, float, float, float] | None:
    if not value:
        return None
    parts = value.split(",")
    if len(parts) != 4:
        return None
    try:
        return tuple(float(part) for part in parts)  # type: ignore[return-value]
    except ValueError:
        return None


def normalized_pixel_digest(image: Image.Image) -> str:
    normalized = image.convert("RGBA")
    digest = hashlib.sha256()
    digest.update(f"{normalized.width}x{normalized.height}:RGBA\0".encode("ascii"))
    digest.update(normalized.tobytes())
    return digest.hexdigest()


def embedded_png_pixel_digest(href: str) -> str | None:
    prefix = "data:image/png;base64,"
    if not href.startswith(prefix):
        return None
    try:
        payload = base64.b64decode(href[len(prefix) :], validate=True)
        with Image.open(io.BytesIO(payload)) as image:
            image.load()
            return normalized_pixel_digest(image)
    except (ValueError, OSError):
        return None


def view_box_bbox(value: str | None) -> tuple[float, float, float, float] | None:
    if not value:
        return None
    parts = re.split(r"[\s,]+", value.strip())
    if len(parts) != 4:
        return None
    try:
        return tuple(float(part) for part in parts)  # type: ignore[return-value]
    except ValueError:
        return None


def boxes_close(
    actual: tuple[float, float, float, float] | None,
    expected: tuple[float, float, float, float],
    *,
    tolerance: float = 0.01,
) -> bool:
    return actual is not None and all(
        abs(actual_value - expected_value) <= tolerance
        for actual_value, expected_value in zip(actual, expected)
    )


def rectangle_union_area(boxes: list[tuple[float, float, float, float]]) -> float:
    if not boxes:
        return 0.0
    x_values = sorted({box[0] for box in boxes} | {box[0] + box[2] for box in boxes})
    total = 0.0
    for left, right in zip(x_values, x_values[1:]):
        intervals = sorted(
            (box[1], box[1] + box[3])
            for box in boxes
            if box[0] < right and box[0] + box[2] > left
        )
        if not intervals:
            continue
        covered_y = 0.0
        start, end = intervals[0]
        for next_start, next_end in intervals[1:]:
            if next_start > end:
                covered_y += end - start
                start, end = next_start, next_end
            else:
                end = max(end, next_end)
        covered_y += end - start
        total += (right - left) * covered_y
    return total


def clipped_box(
    box: tuple[float, float, float, float],
    bounds: tuple[float, float, float, float],
) -> tuple[float, float, float, float] | None:
    left = max(box[0], bounds[0])
    top = max(box[1], bounds[1])
    right = min(box[0] + box[2], bounds[0] + bounds[2])
    bottom = min(box[1] + box[3], bounds[1] + bounds[3])
    if right <= left or bottom <= top:
        return None
    return left, top, right - left, bottom - top


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_path_data(data: str | None) -> tuple[list[tuple[str, tuple[float, ...]]], list[str]]:
    if not data or not data.strip():
        return [], ["path_data_missing"]
    tokens = []
    cursor = 0
    for match in PATH_TOKEN.finditer(data):
        gap = data[cursor : match.start()]
        if gap.strip(" ,\t\r\n"):
            return [], [f"invalid_path_token:{gap.strip()}"]
        tokens.append(match.group(0))
        cursor = match.end()
    tail = data[cursor:]
    if tail.strip(" ,\t\r\n"):
        return [], [f"invalid_path_token:{tail.strip()}"]
    if not tokens or tokens[0] not in {"M", "m"}:
        return [], ["path_must_start_with_moveto"]

    segments: list[tuple[str, tuple[float, ...]]] = []
    issues = []
    index = 0
    command: str | None = None
    while index < len(tokens):
        token = tokens[index]
        if token.isalpha():
            command = token
            index += 1
            if command in {"Z", "z"}:
                segments.append((command, ()))
                command = None
                continue
        if command is None:
            issues.append("path_numbers_without_command")
            break
        upper = command.upper()
        parameter_count = PATH_PARAMETER_COUNTS.get(upper)
        if parameter_count is None:
            issues.append(f"unsupported_path_command:{command}")
            break
        values = []
        while index < len(tokens) and not tokens[index].isalpha():
            values.append(float(tokens[index]))
            index += 1
        if not values or len(values) % parameter_count:
            issues.append(f"wrong_parameter_count:{command}:{len(values)}")
            continue
        for group_index in range(0, len(values), parameter_count):
            group = tuple(values[group_index : group_index + parameter_count])
            emitted_command = command
            if upper == "M" and group_index:
                emitted_command = "l" if command == "m" else "L"
            if emitted_command.upper() == "A":
                if group[0] < 0 or group[1] < 0:
                    issues.append("arc_radius_negative")
                if group[3] not in {0.0, 1.0} or group[4] not in {0.0, 1.0}:
                    issues.append("arc_flag_invalid")
            segments.append((emitted_command, group))
    return segments, issues


def point_on_circle(cx: float, cy: float, radius: float, angle_deg: float) -> tuple[float, float]:
    angle = math.radians(angle_deg)
    return cx + radius * math.cos(angle), cy + radius * math.sin(angle)


def close_enough(actual: float, expected: float, tolerance: float) -> bool:
    return abs(actual - expected) <= tolerance


def expected_arc_delta(start_angle_deg: float, end_angle_deg: float, clockwise: bool) -> float:
    delta = (
        (end_angle_deg - start_angle_deg) % 360
        if clockwise
        else (start_angle_deg - end_angle_deg) % 360
    )
    return 360.0 if math.isclose(delta, 0.0, abs_tol=1e-9) else delta


def validate_annular_sector(
    element: ET.Element,
    expectation: AnnularSectorExpectation,
) -> list[str]:
    segments, issues = parse_path_data(element.attrib.get("d"))
    if issues:
        return issues
    if expectation.inner_radius <= 0 or expectation.outer_radius <= expectation.inner_radius:
        return ["annular_sector_contract_radii_invalid"]
    delta = expected_arc_delta(
        expectation.start_angle_deg, expectation.end_angle_deg, expectation.clockwise
    )
    if math.isclose(delta, 360.0, abs_tol=1e-9):
        if [command for command, _ in segments] != ["M", "A", "A", "M", "A", "A", "Z"]:
            return ["full_annular_sector_must_be_M_A_A_M_A_A_Z"]
        outer_sweep = 1.0 if expectation.clockwise else 0.0
        inner_sweep = 1.0 - outer_sweep
        midpoint_angle = expectation.start_angle_deg + (180 if expectation.clockwise else -180)
        outer_start = point_on_circle(
            expectation.cx, expectation.cy, expectation.outer_radius, expectation.start_angle_deg
        )
        outer_mid = point_on_circle(
            expectation.cx, expectation.cy, expectation.outer_radius, midpoint_angle
        )
        inner_start = point_on_circle(
            expectation.cx, expectation.cy, expectation.inner_radius, expectation.start_angle_deg
        )
        inner_mid = point_on_circle(
            expectation.cx, expectation.cy, expectation.inner_radius, midpoint_angle
        )
        move_outer, outer_one, outer_two, move_inner, inner_one, inner_two, _ = (
            values for _, values in segments
        )
        checks = (
            (move_outer[0], outer_start[0], "outer_start_x"),
            (move_outer[1], outer_start[1], "outer_start_y"),
            (outer_one[0], expectation.outer_radius, "outer_one_rx"),
            (outer_one[1], expectation.outer_radius, "outer_one_ry"),
            (outer_one[2], 0.0, "outer_one_rotation"),
            (outer_one[3], 0.0, "outer_one_large_arc"),
            (outer_one[4], outer_sweep, "outer_one_sweep"),
            (outer_one[5], outer_mid[0], "outer_mid_x"),
            (outer_one[6], outer_mid[1], "outer_mid_y"),
            (outer_two[0], expectation.outer_radius, "outer_two_rx"),
            (outer_two[1], expectation.outer_radius, "outer_two_ry"),
            (outer_two[2], 0.0, "outer_two_rotation"),
            (outer_two[3], 0.0, "outer_two_large_arc"),
            (outer_two[4], outer_sweep, "outer_two_sweep"),
            (outer_two[5], outer_start[0], "outer_close_x"),
            (outer_two[6], outer_start[1], "outer_close_y"),
            (move_inner[0], inner_start[0], "inner_start_x"),
            (move_inner[1], inner_start[1], "inner_start_y"),
            (inner_one[0], expectation.inner_radius, "inner_one_rx"),
            (inner_one[1], expectation.inner_radius, "inner_one_ry"),
            (inner_one[2], 0.0, "inner_one_rotation"),
            (inner_one[3], 0.0, "inner_one_large_arc"),
            (inner_one[4], inner_sweep, "inner_one_sweep"),
            (inner_one[5], inner_mid[0], "inner_mid_x"),
            (inner_one[6], inner_mid[1], "inner_mid_y"),
            (inner_two[0], expectation.inner_radius, "inner_two_rx"),
            (inner_two[1], expectation.inner_radius, "inner_two_ry"),
            (inner_two[2], 0.0, "inner_two_rotation"),
            (inner_two[3], 0.0, "inner_two_large_arc"),
            (inner_two[4], inner_sweep, "inner_two_sweep"),
            (inner_two[5], inner_start[0], "inner_close_x"),
            (inner_two[6], inner_start[1], "inner_close_y"),
        )
        return [
            name
            for actual, expected, name in checks
            if not close_enough(actual, expected, expectation.tolerance)
        ]
    if [command for command, _ in segments] != ["M", "A", "L", "A", "Z"]:
        return ["annular_sector_must_be_M_A_L_A_Z"]
    large_arc = 1.0 if delta > 180 else 0.0
    outer_sweep = 1.0 if expectation.clockwise else 0.0
    inner_sweep = 1.0 - outer_sweep
    outer_start = point_on_circle(
        expectation.cx, expectation.cy, expectation.outer_radius, expectation.start_angle_deg
    )
    outer_end = point_on_circle(
        expectation.cx, expectation.cy, expectation.outer_radius, expectation.end_angle_deg
    )
    inner_end = point_on_circle(
        expectation.cx, expectation.cy, expectation.inner_radius, expectation.end_angle_deg
    )
    inner_start = point_on_circle(
        expectation.cx, expectation.cy, expectation.inner_radius, expectation.start_angle_deg
    )
    move = segments[0][1]
    outer_arc = segments[1][1]
    line = segments[2][1]
    inner_arc = segments[3][1]
    checks = (
        (move[0], outer_start[0], "outer_start_x"),
        (move[1], outer_start[1], "outer_start_y"),
        (outer_arc[0], expectation.outer_radius, "outer_rx"),
        (outer_arc[1], expectation.outer_radius, "outer_ry"),
        (outer_arc[2], 0.0, "outer_rotation"),
        (outer_arc[3], large_arc, "outer_large_arc"),
        (outer_arc[4], outer_sweep, "outer_sweep"),
        (outer_arc[5], outer_end[0], "outer_end_x"),
        (outer_arc[6], outer_end[1], "outer_end_y"),
        (line[0], inner_end[0], "inner_end_x"),
        (line[1], inner_end[1], "inner_end_y"),
        (inner_arc[0], expectation.inner_radius, "inner_rx"),
        (inner_arc[1], expectation.inner_radius, "inner_ry"),
        (inner_arc[2], 0.0, "inner_rotation"),
        (inner_arc[3], large_arc, "inner_large_arc"),
        (inner_arc[4], inner_sweep, "inner_sweep"),
        (inner_arc[5], inner_start[0], "inner_start_x"),
        (inner_arc[6], inner_start[1], "inner_start_y"),
    )
    return [name for actual, expected, name in checks if not close_enough(actual, expected, expectation.tolerance)]


def validate_arc(element: ET.Element, expectation: ArcExpectation) -> list[str]:
    segments, issues = parse_path_data(element.attrib.get("d"))
    if issues:
        return issues
    if expectation.radius <= 0:
        return ["arc_contract_radius_invalid"]
    delta = expected_arc_delta(
        expectation.start_angle_deg, expectation.end_angle_deg, expectation.clockwise
    )
    if math.isclose(delta, 360.0, abs_tol=1e-9):
        if [command for command, _ in segments] != ["M", "A", "A"]:
            return ["full_arc_must_be_open_M_A_A"]
        sweep = 1.0 if expectation.clockwise else 0.0
        midpoint_angle = expectation.start_angle_deg + (180 if expectation.clockwise else -180)
        start = point_on_circle(
            expectation.cx, expectation.cy, expectation.radius, expectation.start_angle_deg
        )
        midpoint = point_on_circle(
            expectation.cx, expectation.cy, expectation.radius, midpoint_angle
        )
        move, first, second = (values for _, values in segments)
        checks = (
            (move[0], start[0], "start_x"),
            (move[1], start[1], "start_y"),
            (first[0], expectation.radius, "first_rx"),
            (first[1], expectation.radius, "first_ry"),
            (first[2], 0.0, "first_rotation"),
            (first[3], 0.0, "first_large_arc"),
            (first[4], sweep, "first_sweep"),
            (first[5], midpoint[0], "midpoint_x"),
            (first[6], midpoint[1], "midpoint_y"),
            (second[0], expectation.radius, "second_rx"),
            (second[1], expectation.radius, "second_ry"),
            (second[2], 0.0, "second_rotation"),
            (second[3], 0.0, "second_large_arc"),
            (second[4], sweep, "second_sweep"),
            (second[5], start[0], "close_x"),
            (second[6], start[1], "close_y"),
        )
        return [
            name
            for actual, expected, name in checks
            if not close_enough(actual, expected, expectation.tolerance)
        ]
    if [command for command, _ in segments] != ["M", "A"]:
        return ["arc_must_be_open_M_A"]
    large_arc = 1.0 if delta > 180 else 0.0
    sweep = 1.0 if expectation.clockwise else 0.0
    start = point_on_circle(
        expectation.cx, expectation.cy, expectation.radius, expectation.start_angle_deg
    )
    end = point_on_circle(
        expectation.cx, expectation.cy, expectation.radius, expectation.end_angle_deg
    )
    move = segments[0][1]
    arc = segments[1][1]
    checks = (
        (move[0], start[0], "start_x"),
        (move[1], start[1], "start_y"),
        (arc[0], expectation.radius, "rx"),
        (arc[1], expectation.radius, "ry"),
        (arc[2], 0.0, "rotation"),
        (arc[3], large_arc, "large_arc"),
        (arc[4], sweep, "sweep"),
        (arc[5], end[0], "end_x"),
        (arc[6], end[1], "end_y"),
    )
    return [name for actual, expected, name in checks if not close_enough(actual, expected, expectation.tolerance)]


def plain_text(element: ET.Element) -> str:
    return "".join(element.itertext()).strip()


def external_reference(value: str, *, allow_data_image: bool = True) -> bool:
    stripped = value.strip().strip("'\"")
    if stripped.startswith("#"):
        return False
    if allow_data_image and stripped.startswith("data:image/"):
        return False
    return bool(stripped)


def recipe_text(element: dict) -> tuple[str, bool]:
    runs = element.get("runs", [])
    if runs:
        content = "".join(str(run.get("text", "")) for run in runs)
        return content, any(run.get("baseline_shift") == "sub" for run in runs)
    return str(element.get("text", "")), False


def recipe_stroke(element: dict, defaults: dict) -> tuple[str, float] | None:
    if "stroke_width_mm" in element:
        return element["id"], float(element["stroke_width_mm"])
    if element.get("type") in {"line", "rect", "ellipse", "polyline"}:
        return element["id"], float(defaults.get("stroke_width_mm", 0.2))
    return None


def flatten_recipe_elements(
    elements: list[dict], parent_id: str | None = None
) -> list[tuple[dict, str | None]]:
    flattened = []
    for element in elements:
        flattened.append((element, parent_id))
        if element.get("type") == "group":
            flattened.extend(flatten_recipe_elements(element.get("children", []), element["id"]))
    return flattened


def contract_from_recipe(recipe: dict) -> SvgAuditContract:
    defaults = recipe.get("defaults", {})
    declared = recipe.get("contract", {})
    flattened = flatten_recipe_elements(recipe.get("elements", []))
    elements = [element for element, _ in flattened]
    text_elements = [element for element in elements if element.get("type") in {"text", "text_path"}]
    text_details = [(element["id"], *recipe_text(element)) for element in text_elements]
    stroke_details = [recipe_stroke(element, defaults) for element in elements]
    type_map = {
        "text": "text",
        "text_path": "text",
        "line": "line",
        "rect": "rect",
        "ellipse": "ellipse",
        "polyline": "polyline",
        "polygon": "polygon",
        "path": "path",
        "arc": "path",
        "annular_sector": "path",
        "group": "g",
    }
    canvas = recipe["canvas"]
    scale = float(canvas["print_width_mm"]) * CSS_PX_PER_MM / float(canvas["width_px"])
    annular_sectors = tuple(
        AnnularSectorExpectation(
            element_id=element["id"],
            cx=float(element["cx_px"]) * scale,
            cy=float(element["cy_px"]) * scale,
            inner_radius=float(element["inner_radius_px"]) * scale,
            outer_radius=float(element["outer_radius_px"]) * scale,
            start_angle_deg=float(element["start_angle_deg"]),
            end_angle_deg=float(element["end_angle_deg"]),
            clockwise=bool(element.get("clockwise", True)),
            tolerance=max(0.01, scale * 0.02),
        )
        for element in elements
        if element.get("type") == "annular_sector"
    )
    arcs = tuple(
        ArcExpectation(
            element_id=(
                f"{element['id']}__curve" if element.get("type") == "text_path" else element["id"]
            ),
            cx=float(element["cx_px"]) * scale,
            cy=float(element["cy_px"]) * scale,
            radius=float(element["radius_px"]) * scale,
            start_angle_deg=float(element["start_angle_deg"]),
            end_angle_deg=float(element["end_angle_deg"]),
            clockwise=bool(element.get("clockwise", True)),
            tolerance=max(0.01, scale * 0.02),
        )
        for element in elements
        if element.get("type") in {"arc", "text_path"}
    )
    gradients = recipe.get("gradients", [])
    atomic_specs = []
    for region in recipe.get("atomic_rasters", []):
        source_box = tuple(float(value) for value in region["source_bbox_px"])
        canvas_box = tuple(float(value) for value in region["canvas_bbox_px"])
        atomic_specs.append(
            AtomicRasterExpectation(
                element_id=region["id"],
                source_file=Path(region["source_file"]).name,
                cleaned_file=Path(region["cleaned_file"]).name,
                source_bbox_px=source_box,
                canvas_bbox_px=canvas_box,
                canvas_bbox_user=tuple(value * scale for value in canvas_box),
                evidence=bool(region["evidence"]),
            )
        )
    atomic_by_id = {region["id"]: region for region in recipe.get("atomic_rasters", [])}
    occlusion_specs = []
    for mask in recipe.get("annotation_occlusion_masks", []):
        atomic = atomic_by_id[mask["atomic_raster_id"]]
        source_x, source_y, source_width, source_height = (
            float(value) for value in atomic["source_bbox_px"]
        )
        canvas_x, canvas_y, canvas_width, canvas_height = (
            float(value) for value in atomic["canvas_bbox_px"]
        )
        mask_x, mask_y, mask_width, mask_height = (
            float(value) for value in mask["rect_px"]
        )
        canvas_rect_px = (
            canvas_x + (mask_x - source_x) * canvas_width / source_width,
            canvas_y + (mask_y - source_y) * canvas_height / source_height,
            mask_width * canvas_width / source_width,
            mask_height * canvas_height / source_height,
        )
        occlusion_specs.append(
            AnnotationOcclusionExpectation(
                element_id=mask["id"],
                atomic_raster_id=mask["atomic_raster_id"],
                source_rect_px=(mask_x, mask_y, mask_width, mask_height),
                canvas_rect_user=tuple(value * scale for value in canvas_rect_px),
                mode=mask["mode"],
                fill=mask["fill"],
                max_area_fraction=float(mask["max_area_fraction"]),
                evidence_change_contract=mask["evidence_change_contract"],
                source_crop_sha256=mask["source_crop_sha256"],
                old_annotation_risk=mask["old_annotation_risk"],
                approval_status=mask["approval_status"],
                approved_by=str(mask.get("approved_by", "")),
                approval_note=str(mask.get("approval_note", "")),
                replacement_element_ids=tuple(mask["replacement_element_ids"]),
            )
        )
    for region in recipe.get("raster_regions", []):
        source_box = tuple(float(value) for value in region["source_rect_px"])
        canvas_box = tuple(float(value) for value in region.get("dest_rect_px", source_box))
        atomic_specs.append(
            AtomicRasterExpectation(
                element_id=region["id"],
                source_file=Path(recipe["source_image"]).name,
                cleaned_file=None,
                source_bbox_px=source_box,
                canvas_bbox_px=canvas_box,
                canvas_bbox_user=tuple(value * scale for value in canvas_box),
                evidence=bool(region["atomic_raster_unit"])
                and not bool(region["contains_reconstructable_content"]),
            )
        )
    return SvgAuditContract(
        font_family=str(declared.get("required_font_family", defaults.get("font_family", "Times New Roman"))),
        font_size_pt=float(declared.get("required_font_size_pt", defaults.get("font_size_pt", 8.5))),
        expected_text_count=len(text_elements),
        required_ids=tuple(element["id"] for element in elements),
        expected_width_mm=float(recipe["canvas"]["print_width_mm"]),
        expected_text=tuple((element_id, content) for element_id, content, _ in text_details),
        required_subscripts=tuple(element_id for element_id, _, subscript in text_details if subscript),
        stroke_expectations=tuple(stroke for stroke in stroke_details if stroke is not None),
        require_atomic_rasters=bool(declared.get("require_atomic_rasters", False)),
        require_no_raster=bool(declared.get("require_zero_rasters", False)),
        enforce_declared_atomic_rasters=bool(declared.get("require_atomic_rasters", False)),
        atomic_rasters=tuple(atomic_specs),
        annotation_occlusions=tuple(occlusion_specs),
        required_element_types=tuple(
            (element["id"], type_map[element["type"]])
            for element in elements
            if element.get("type") in type_map
        ),
        required_parent_ids=tuple(
            (element["id"], parent_id)
            for element, parent_id in flattened
            if parent_id is not None
        ),
        required_gradient_ids=tuple(gradient["id"] for gradient in gradients),
        require_user_space_gradients=bool(gradients),
        expected_fill_gradients=tuple(
            (element["id"], element["fill_gradient"])
            for element in elements
            if element.get("fill_gradient")
        ),
        required_text_path_ids=tuple(
            element["id"] for element in text_elements if element.get("type") == "text_path"
        ),
        expected_text_path_curves=tuple(
            (element["id"], f"{element['id']}__curve")
            for element in text_elements
            if element.get("type") == "text_path"
        ),
        arcs=arcs,
        annular_sectors=annular_sectors,
    )


def audit_svg(
    path: Path,
    contract: SvgAuditContract,
) -> dict:
    root = ET.parse(path).getroot()
    physical_font_user_unit_to_pt = None
    if root.attrib.get("data-physical-font-scaling") == "viewBox-to-mm":
        width_match = re.fullmatch(r"\s*([0-9.]+)mm\s*", root.attrib.get("width", ""))
        view_box = root.attrib.get("viewBox", "").replace(",", " ").split()
        if width_match and len(view_box) == 4:
            try:
                view_box_width = float(view_box[2])
                if view_box_width > 0:
                    physical_font_user_unit_to_pt = (
                        float(width_match.group(1)) * PT_PER_MM / view_box_width
                    )
            except ValueError:
                physical_font_user_unit_to_pt = None
    ids = [element.attrib["id"] for element in root.iter() if "id" in element.attrib]
    texts = list(root.iter(f"{SVG_NS}text"))
    images = list(root.iter(f"{SVG_NS}image"))
    paths = list(root.iter(f"{SVG_NS}path"))
    text_paths = list(root.iter(f"{SVG_NS}textPath"))
    gradients = list(root.iter(f"{SVG_NS}linearGradient")) + list(
        root.iter(f"{SVG_NS}radialGradient")
    )
    raster_elements = images + list(root.iter(f"{SVG_NS}feImage"))
    scripts = list(root.iter(f"{SVG_NS}script"))
    foreign_objects = list(root.iter(f"{SVG_NS}foreignObject"))
    remote_images = []
    external_references = []
    font_issues = []
    size_issues = []
    stroke_issues = []
    event_handlers = []
    missing_source_images = []
    text_content_issues = []
    text_format_issues = []
    missing_required_ids = []
    physical_size_issues = []
    atomic_raster_issues = []
    raster_contract_issues = []
    path_data_issues = []
    gradient_reference_issues = []
    text_path_issues = []
    element_type_issues = []
    topology_issues = []
    arc_issues = []
    annular_sector_issues = []
    annotation_occlusion_issues = []

    view_box = view_box_bbox(root.attrib.get("viewBox"))
    expected_atomic = {expectation.element_id: expectation for expectation in contract.atomic_rasters}
    actual_image_ids = {image.attrib.get("id") for image in images}
    if contract.enforce_declared_atomic_rasters:
        for unexpected_id in sorted(actual_image_ids - set(expected_atomic), key=lambda value: str(value)):
            atomic_raster_issues.append({"id": unexpected_id, "issue": "undeclared_raster"})
        for missing_id in sorted(set(expected_atomic) - actual_image_ids):
            atomic_raster_issues.append({"id": missing_id, "issue": "declared_raster_missing"})
        for element in root.iter(f"{SVG_NS}feImage"):
            atomic_raster_issues.append(
                {"id": element.attrib.get("id"), "issue": "undeclared_filter_raster"}
            )

    by_id = {element.attrib.get("id"): element for element in root.iter() if element.attrib.get("id")}
    parent_by_child = {child: parent for parent in root.iter() for child in parent}

    for element in root.iter():
        for key, value in element.attrib.items():
            if key.lower().startswith("on"):
                event_handlers.append({"id": element.attrib.get("id"), "attribute": key})
            local_key = key.rsplit("}", 1)[-1].lower()
            if local_key == "href" and external_reference(
                value, allow_data_image=element.tag == f"{SVG_NS}image"
            ):
                external_references.append({"id": element.attrib.get("id"), "href": value})
            if "url(" in value.lower():
                for match in re.findall(r"url\(([^)]+)\)", value, flags=re.IGNORECASE):
                    if external_reference(match, allow_data_image=False):
                        external_references.append({"id": element.attrib.get("id"), "href": match})
        if element.tag == f"{SVG_NS}style" and element.text:
            for match in re.findall(r"url\(([^)]+)\)", element.text, flags=re.IGNORECASE):
                if external_reference(match, allow_data_image=False):
                    external_references.append({"id": "style", "href": match})
    for image in images:
        href = image.attrib.get("href", image.attrib.get("{http://www.w3.org/1999/xlink}href", ""))
        if not href.startswith("data:image/"):
            remote_images.append(href)
        if not (image.attrib.get("data-source-file") or image.attrib.get("data-cleaned-file")):
            missing_source_images.append(image.attrib.get("id"))
        if contract.require_atomic_rasters:
            if not href.startswith("data:image/png;base64,"):
                atomic_raster_issues.append(
                    {"id": image.attrib.get("id"), "issue": "atomic_raster_payload_not_png"}
                )
            current = image
            while current is not None:
                if current.attrib.get("transform"):
                    atomic_raster_issues.append(
                        {"id": image.attrib.get("id"), "issue": "transformed_raster"}
                    )
                    break
                current = parent_by_child.get(current)
            if (
                image.attrib.get("display") == "none"
                or image.attrib.get("visibility") == "hidden"
                or image.attrib.get("opacity") == "0"
            ):
                atomic_raster_issues.append(
                    {"id": image.attrib.get("id"), "issue": "hidden_raster"}
                )
            required_metadata = (
                "data-raster-reason",
                "data-atomic-raster-unit",
                "data-contains-reconstructable-content",
                "data-decomposition-note",
                "data-cleaned-file",
                "data-source-bbox-px",
                "data-canvas-bbox-px",
                "data-evidence",
                "data-nonuniform-scale",
            )
            missing_metadata = [key for key in required_metadata if not image.attrib.get(key)]
            if missing_metadata:
                atomic_raster_issues.append(
                    {"id": image.attrib.get("id"), "missing_metadata": missing_metadata}
                )
            if image.attrib.get("data-atomic-raster-unit") != "true":
                atomic_raster_issues.append({"id": image.attrib.get("id"), "issue": "not_atomic"})
            if image.attrib.get("data-contains-reconstructable-content") != "false":
                atomic_raster_issues.append(
                    {"id": image.attrib.get("id"), "issue": "contains_reconstructable_content"}
                )
            if image.attrib.get("data-evidence") != "true":
                atomic_raster_issues.append({"id": image.attrib.get("id"), "issue": "not_evidence"})
            if image.attrib.get("data-nonuniform-scale") != "false":
                atomic_raster_issues.append(
                    {"id": image.attrib.get("id"), "issue": "nonuniform_scale_not_forbidden"}
                )
            if image.attrib.get("preserveAspectRatio") != "xMidYMid meet":
                atomic_raster_issues.append(
                    {"id": image.attrib.get("id"), "issue": "unsafe_preserve_aspect_ratio"}
                )
            expectation = expected_atomic.get(image.attrib.get("id"))
            if expectation is not None:
                if image.attrib.get("data-source-file") != expectation.source_file:
                    atomic_raster_issues.append(
                        {"id": expectation.element_id, "issue": "source_file_mismatch"}
                    )
                if expectation.cleaned_file is not None and image.attrib.get(
                    "data-cleaned-file"
                ) != expectation.cleaned_file:
                    atomic_raster_issues.append(
                        {"id": expectation.element_id, "issue": "cleaned_file_mismatch"}
                    )
                if not boxes_close(
                    metadata_bbox(image.attrib.get("data-source-bbox-px")),
                    expectation.source_bbox_px,
                ):
                    atomic_raster_issues.append(
                        {"id": expectation.element_id, "issue": "source_bbox_mismatch"}
                    )
                if not boxes_close(
                    metadata_bbox(image.attrib.get("data-canvas-bbox-px")),
                    expectation.canvas_bbox_px,
                ):
                    atomic_raster_issues.append(
                        {"id": expectation.element_id, "issue": "canvas_bbox_metadata_mismatch"}
                    )
                actual_geometry = tuple(
                    numeric_attribute(image.attrib.get(name))
                    for name in ("x", "y", "width", "height")
                )
                if any(value is None for value in actual_geometry) or not boxes_close(
                    actual_geometry, expectation.canvas_bbox_user  # type: ignore[arg-type]
                ):
                    atomic_raster_issues.append(
                        {"id": expectation.element_id, "issue": "canvas_bbox_geometry_mismatch"}
                    )
                if image.attrib.get("data-evidence") != str(expectation.evidence).lower():
                    atomic_raster_issues.append(
                        {"id": expectation.element_id, "issue": "evidence_flag_mismatch"}
                    )
            actual_box_values = tuple(
                numeric_attribute(image.attrib.get(name))
                for name in ("x", "y", "width", "height")
            )
            if view_box is not None and all(value is not None for value in actual_box_values):
                actual_box = actual_box_values  # type: ignore[assignment]
                if boxes_close(actual_box, view_box, tolerance=0.01):
                    atomic_raster_issues.append(
                        {"id": image.attrib.get("id"), "issue": "full_canvas_raster"}
                    )
    if contract.require_atomic_rasters and view_box is not None:
        image_boxes = []
        for image in images:
            values = tuple(
                numeric_attribute(image.attrib.get(name))
                for name in ("x", "y", "width", "height")
            )
            if all(value is not None for value in values):
                clipped = clipped_box(values, view_box)  # type: ignore[arg-type]
                if clipped is not None:
                    image_boxes.append(clipped)
        if image_boxes and rectangle_union_area(image_boxes) >= view_box[2] * view_box[3] - 0.01:
            atomic_raster_issues.append({"id": None, "issue": "rasters_collectively_cover_canvas"})

    expected_occlusions = {
        expectation.element_id: expectation for expectation in contract.annotation_occlusions
    }
    actual_occlusions = {
        element.attrib.get("id"): element
        for element in root.iter()
        if element.attrib.get("data-occlusion-mode")
    }
    for unexpected_id in sorted(set(actual_occlusions) - set(expected_occlusions)):
        annotation_occlusion_issues.append(
            {"id": unexpected_id, "issue": "undeclared_annotation_occlusion"}
        )
    undeclared_group = by_id.get("annotation-occlusion-masks")
    if not expected_occlusions and undeclared_group is not None:
        annotation_occlusion_issues.append(
            {"id": "annotation-occlusion-masks", "issue": "undeclared_mask_group"}
        )
    if expected_occlusions:
        occlusion_group = by_id.get("annotation-occlusion-masks")
        if occlusion_group is None or local_name(occlusion_group.tag) != "g":
            annotation_occlusion_issues.append(
                {"id": "annotation-occlusion-masks", "issue": "mask_group_missing_or_wrong_type"}
            )
        order = {element: index for index, element in enumerate(root.iter())}
        atomic_expectations = {
            expectation.element_id: expectation for expectation in contract.atomic_rasters
        }
        for mask_id, expectation in expected_occlusions.items():
            element = by_id.get(mask_id)
            if element is None:
                annotation_occlusion_issues.append(
                    {"id": mask_id, "issue": "declared_annotation_occlusion_missing"}
                )
                continue
            if local_name(element.tag) != "rect":
                annotation_occlusion_issues.append(
                    {"id": mask_id, "issue": "annotation_occlusion_not_rect"}
                )
            if parent_by_child.get(element) is not occlusion_group:
                annotation_occlusion_issues.append(
                    {"id": mask_id, "issue": "annotation_occlusion_wrong_parent"}
                )
            actual_geometry = tuple(
                numeric_attribute(element.attrib.get(name))
                for name in ("x", "y", "width", "height")
            )
            if any(value is None for value in actual_geometry) or not boxes_close(
                actual_geometry, expectation.canvas_rect_user  # type: ignore[arg-type]
            ):
                annotation_occlusion_issues.append(
                    {"id": mask_id, "issue": "annotation_occlusion_geometry_mismatch"}
                )
            expected_metadata = {
                "data-atomic-raster-id": expectation.atomic_raster_id,
                "data-occlusion-mode": expectation.mode,
                "data-evidence-change-contract": expectation.evidence_change_contract,
                "data-source-crop-sha256": expectation.source_crop_sha256,
                "data-old-annotation-risk": expectation.old_annotation_risk,
                "data-approval-status": expectation.approval_status,
                "data-approved-by": expectation.approved_by,
                "data-approval-note": expectation.approval_note,
                "data-replacement-element-ids": ",".join(expectation.replacement_element_ids),
            }
            for key, expected_value in expected_metadata.items():
                if element.attrib.get(key, "") != expected_value:
                    annotation_occlusion_issues.append(
                        {
                            "id": mask_id,
                            "issue": "annotation_occlusion_metadata_mismatch",
                            "field": key,
                        }
                    )
            if not boxes_close(
                metadata_bbox(element.attrib.get("data-source-rect-px")),
                expectation.source_rect_px,
            ):
                annotation_occlusion_issues.append(
                    {"id": mask_id, "issue": "annotation_occlusion_source_rect_mismatch"}
                )
            actual_max_fraction = numeric_attribute(element.attrib.get("data-max-area-fraction"))
            if actual_max_fraction is None or abs(
                actual_max_fraction - expectation.max_area_fraction
            ) > 1e-9:
                annotation_occlusion_issues.append(
                    {"id": mask_id, "issue": "annotation_occlusion_area_contract_mismatch"}
                )
            if style_value(element, "fill") != expectation.fill or style_value(element, "stroke") != "none":
                annotation_occlusion_issues.append(
                    {"id": mask_id, "issue": "annotation_occlusion_paint_mismatch"}
                )
            current = element
            unsafe_visual_state = False
            while current is not None:
                opacity = numeric_attribute(style_value(current, "opacity"))
                fill_opacity = numeric_attribute(style_value(current, "fill-opacity"))
                if (
                    style_value(current, "display") == "none"
                    or style_value(current, "visibility") == "hidden"
                    or (opacity is not None and abs(opacity - 1.0) > 1e-9)
                    or (fill_opacity is not None and abs(fill_opacity - 1.0) > 1e-9)
                    or current.attrib.get("transform")
                    or any(style_value(current, key) for key in ("clip-path", "mask", "filter"))
                ):
                    unsafe_visual_state = True
                    break
                if current is occlusion_group:
                    break
                current = parent_by_child.get(current)
            if unsafe_visual_state or numeric_attribute(element.attrib.get("rx")) not in {None, 0} or numeric_attribute(
                element.attrib.get("ry")
            ) not in {None, 0}:
                annotation_occlusion_issues.append(
                    {"id": mask_id, "issue": "annotation_occlusion_hidden_clipped_or_transformed"}
                )
            if expectation.evidence_change_contract != "source_pixels_immutable":
                annotation_occlusion_issues.append(
                    {"id": mask_id, "issue": "unsafe_evidence_change_contract"}
                )
            if expectation.old_annotation_risk != "confirmed_occluded":
                annotation_occlusion_issues.append(
                    {
                        "id": mask_id,
                        "issue": "old_annotation_residual_risk",
                        "status": expectation.old_annotation_risk,
                    }
                )
            if expectation.approval_status != "approved" or not (
                expectation.approved_by.strip() and expectation.approval_note.strip()
            ):
                annotation_occlusion_issues.append(
                    {
                        "id": mask_id,
                        "issue": "annotation_occlusion_not_approved",
                        "status": expectation.approval_status,
                    }
                )
            replacement_elements = [by_id.get(value) for value in expectation.replacement_element_ids]
            if any(value is None for value in replacement_elements):
                annotation_occlusion_issues.append(
                    {"id": mask_id, "issue": "replacement_element_missing"}
                )
            elif not any(
                local_name(value.tag) == "text" for value in replacement_elements if value is not None
            ):
                annotation_occlusion_issues.append(
                    {"id": mask_id, "issue": "live_text_replacement_missing"}
                )
            elif any(
                order[element] >= order[value]
                for value in replacement_elements
                if value is not None
            ):
                annotation_occlusion_issues.append(
                    {"id": mask_id, "issue": "replacement_not_above_occlusion"}
                )
            else:
                for replacement in replacement_elements:
                    current = replacement
                    while current is not None:
                        opacity = numeric_attribute(style_value(current, "opacity"))
                        if (
                            style_value(current, "display") == "none"
                            or style_value(current, "visibility") == "hidden"
                            or (opacity is not None and abs(opacity - 1.0) > 1e-9)
                        ):
                            annotation_occlusion_issues.append(
                                {"id": mask_id, "issue": "replacement_element_hidden"}
                            )
                            current = None
                            break
                        current = parent_by_child.get(current)
            atomic_image = by_id.get(expectation.atomic_raster_id)
            atomic_expectation = atomic_expectations.get(expectation.atomic_raster_id)
            if atomic_image is None or local_name(atomic_image.tag) != "image" or atomic_expectation is None:
                annotation_occlusion_issues.append(
                    {"id": mask_id, "issue": "referenced_atomic_raster_missing"}
                )
            else:
                href = atomic_image.attrib.get(
                    "href", atomic_image.attrib.get("{http://www.w3.org/1999/xlink}href", "")
                )
                actual_digest = embedded_png_pixel_digest(href)
                source_digest = atomic_image.attrib.get("data-source-crop-sha256")
                declared_embedded_digest = atomic_image.attrib.get("data-embedded-crop-sha256")
                if (
                    actual_digest is None
                    or source_digest is None
                    or declared_embedded_digest is None
                    or source_digest != expectation.source_crop_sha256
                    or actual_digest != source_digest
                    or actual_digest != declared_embedded_digest
                ):
                    annotation_occlusion_issues.append(
                        {"id": mask_id, "issue": "source_pixels_immutable_digest_mismatch"}
                    )
                source_box = atomic_expectation.source_bbox_px
                mask_box = expectation.source_rect_px
                if not (
                    mask_box[0] >= source_box[0]
                    and mask_box[1] >= source_box[1]
                    and mask_box[0] + mask_box[2] <= source_box[0] + source_box[2]
                    and mask_box[1] + mask_box[3] <= source_box[1] + source_box[3]
                ):
                    annotation_occlusion_issues.append(
                        {"id": mask_id, "issue": "annotation_occlusion_outside_atomic_bounds"}
                    )
                area_fraction = mask_box[2] * mask_box[3] / (source_box[2] * source_box[3])
                if area_fraction > expectation.max_area_fraction + 1e-12:
                    annotation_occlusion_issues.append(
                        {"id": mask_id, "issue": "annotation_occlusion_exceeds_area_contract"}
                    )
    for text in texts:
        font_value = style_value(text, "font-family")
        size_value = font_size_pt(
            style_value(text, "font-size"),
            user_unit_to_pt=physical_font_user_unit_to_pt,
        )
        if font_value != contract.font_family:
            font_issues.append({"id": text.attrib.get("id"), "value": font_value})
        if size_value is None or abs(size_value - contract.font_size_pt) > 0.01:
            size_issues.append({"id": text.attrib.get("id"), "value_pt": size_value})
    if contract.stroke_id_prefix and contract.required_stroke_mm is not None:
        required_pt = contract.required_stroke_mm * PT_PER_MM
        matched_strokes = 0
        for element in root.iter():
            element_id = element.attrib.get("id", "")
            if element_id.startswith(contract.stroke_id_prefix):
                matched_strokes += 1
                value_pt = length_pt(style_value(element, "stroke-width"))
                if value_pt is None or abs(value_pt - required_pt) > 0.01:
                    stroke_issues.append({"id": element_id, "value_pt": value_pt, "required_pt": required_pt})
        if matched_strokes == 0:
            stroke_issues.append({"id_prefix": contract.stroke_id_prefix, "issue": "no_matching_objects"})
    missing_required_ids = [element_id for element_id in contract.required_ids if element_id not in by_id]
    for element_id, required_mm in contract.stroke_expectations:
        element = by_id.get(element_id)
        if element is None:
            continue
        value_pt = length_pt(style_value(element, "stroke-width"))
        required_pt = required_mm * PT_PER_MM
        if value_pt is None or abs(value_pt - required_pt) > 0.01:
            stroke_issues.append({"id": element_id, "value_pt": value_pt, "required_pt": required_pt})
    for element_id, expected in contract.expected_text:
        element = by_id.get(element_id)
        if element is not None and plain_text(element) != expected:
            text_content_issues.append(
                {"id": element_id, "actual": plain_text(element), "expected": expected}
            )
    for element_id in contract.required_subscripts:
        element = by_id.get(element_id)
        if element is not None and not any(
            style_value(child, "baseline-shift") == "sub" for child in element.iter(f"{SVG_NS}tspan")
        ):
            text_format_issues.append({"id": element_id, "required": "subscript_tspan"})
    if contract.expected_width_mm is not None:
        actual_width_pt = length_pt(root.attrib.get("width"))
        expected_width_pt = contract.expected_width_mm * PT_PER_MM
        if actual_width_pt is None or abs(actual_width_pt - expected_width_pt) > 0.01:
            physical_size_issues.append(
                {"dimension": "width", "actual_pt": actual_width_pt, "expected_pt": expected_width_pt}
            )

    for path_element in paths:
        _, issues = parse_path_data(path_element.attrib.get("d"))
        if issues:
            path_data_issues.append({"id": path_element.attrib.get("id"), "issues": issues})

    for element in root.iter():
        for attribute in ("fill", "stroke", "style"):
            value = element.attrib.get(attribute, "")
            for reference in re.findall(r"url\(\s*['\"]?#([^)'\"\s]+)['\"]?\s*\)", value):
                target = by_id.get(reference)
                if target is None:
                    gradient_reference_issues.append(
                        {"id": element.attrib.get("id"), "reference": reference, "issue": "missing"}
                    )
                elif local_name(target.tag) not in {"linearGradient", "radialGradient", "pattern"}:
                    gradient_reference_issues.append(
                        {
                            "id": element.attrib.get("id"),
                            "reference": reference,
                            "issue": "not_a_paint_server",
                        }
                    )
    for gradient_id in contract.required_gradient_ids:
        gradient = by_id.get(gradient_id)
        if gradient is None or local_name(gradient.tag) not in {"linearGradient", "radialGradient"}:
            gradient_reference_issues.append(
                {"id": gradient_id, "issue": "required_gradient_missing_or_wrong_type"}
            )
        elif contract.require_user_space_gradients and gradient.attrib.get("gradientUnits") != "userSpaceOnUse":
            gradient_reference_issues.append(
                {"id": gradient_id, "issue": "gradient_units_not_user_space"}
            )
    for element_id, gradient_id in contract.expected_fill_gradients:
        element = by_id.get(element_id)
        actual_fill = style_value(element, "fill") if element is not None else None
        if actual_fill is None or re.fullmatch(
            rf"url\(\s*['\"]?#{re.escape(gradient_id)}['\"]?\s*\)", actual_fill
        ) is None:
            gradient_reference_issues.append(
                {
                    "id": element_id,
                    "actual": actual_fill,
                    "expected": f"url(#{gradient_id})",
                    "issue": "declared_gradient_not_applied",
                }
            )

    for text_path in text_paths:
        parent = parent_by_child.get(text_path)
        href = text_path.attrib.get(
            "href", text_path.attrib.get("{http://www.w3.org/1999/xlink}href", "")
        )
        target = by_id.get(href[1:]) if href.startswith("#") else None
        if parent is None or local_name(parent.tag) != "text":
            text_path_issues.append(
                {"id": text_path.attrib.get("id"), "issue": "textPath_not_inside_text"}
            )
        if target is None or local_name(target.tag) != "path":
            text_path_issues.append(
                {"id": text_path.attrib.get("id"), "href": href, "issue": "curve_missing_or_not_path"}
            )
        if not plain_text(text_path).strip():
            text_path_issues.append(
                {"id": text_path.attrib.get("id"), "issue": "empty_text_path"}
            )
    for text_id in contract.required_text_path_ids:
        text = by_id.get(text_id)
        descendants = list(text.iter(f"{SVG_NS}textPath")) if text is not None else []
        if text is None or local_name(text.tag) != "text" or len(descendants) != 1:
            text_path_issues.append(
                {"id": text_id, "issue": "required_phrase_level_text_path_missing"}
            )
    for text_id, curve_id in contract.expected_text_path_curves:
        text = by_id.get(text_id)
        descendants = list(text.iter(f"{SVG_NS}textPath")) if text is not None else []
        href = ""
        if len(descendants) == 1:
            href = descendants[0].attrib.get(
                "href", descendants[0].attrib.get("{http://www.w3.org/1999/xlink}href", "")
            )
        if href != f"#{curve_id}":
            text_path_issues.append(
                {
                    "id": text_id,
                    "actual": href,
                    "expected": f"#{curve_id}",
                    "issue": "wrong_text_path_curve",
                }
            )

    for element_id, expected_type in contract.required_element_types:
        element = by_id.get(element_id)
        if element is not None and local_name(element.tag) != expected_type:
            element_type_issues.append(
                {"id": element_id, "actual": local_name(element.tag), "expected": expected_type}
            )
    for child_id, parent_id in contract.required_parent_ids:
        child = by_id.get(child_id)
        parent = parent_by_child.get(child) if child is not None else None
        if parent is None or parent.attrib.get("id") != parent_id:
            topology_issues.append(
                {
                    "id": child_id,
                    "actual_parent": parent.attrib.get("id") if parent is not None else None,
                    "expected_parent": parent_id,
                }
            )
    for expectation in contract.annular_sectors:
        element = by_id.get(expectation.element_id)
        if element is None or local_name(element.tag) != "path":
            continue
        issues = validate_annular_sector(element, expectation)
        if issues:
            annular_sector_issues.append({"id": expectation.element_id, "issues": issues})
    for expectation in contract.arcs:
        element = by_id.get(expectation.element_id)
        if element is None or local_name(element.tag) != "path":
            continue
        issues = validate_arc(element, expectation)
        if issues:
            arc_issues.append({"id": expectation.element_id, "issues": issues})
    if contract.require_no_raster and raster_elements:
        raster_contract_issues.extend(
            {"id": element.attrib.get("id"), "type": local_name(element.tag)}
            for element in raster_elements
        )

    failures = []
    if len(ids) != len(set(ids)):
        failures.append("duplicate_ids")
    if scripts:
        failures.append("scripts_present")
    if foreign_objects:
        failures.append("foreign_objects_present")
    if event_handlers:
        failures.append("event_handlers_present")
    if remote_images:
        failures.append("remote_images_present")
    if external_references:
        failures.append("external_references_present")
    if missing_source_images:
        failures.append("image_source_metadata_missing")
    if not texts:
        failures.append("no_live_text")
    if font_issues:
        failures.append("font_family_mismatch")
    if size_issues:
        failures.append("font_size_mismatch")
    if contract.expected_text_count is not None and len(texts) != contract.expected_text_count:
        failures.append("text_count_mismatch")
    if stroke_issues:
        failures.append("required_stroke_width_mismatch")
    if missing_required_ids:
        failures.append("required_objects_missing")
    if text_content_issues:
        failures.append("text_content_mismatch")
    if text_format_issues:
        failures.append("scientific_text_format_mismatch")
    if physical_size_issues:
        failures.append("physical_size_mismatch")
    if atomic_raster_issues:
        failures.append("atomic_raster_contract_mismatch")
    if raster_contract_issues:
        failures.append("zero_raster_contract_mismatch")
    if path_data_issues:
        failures.append("invalid_path_data")
    if gradient_reference_issues:
        failures.append("gradient_reference_mismatch")
    if text_path_issues:
        failures.append("live_text_path_mismatch")
    if element_type_issues:
        failures.append("required_element_type_mismatch")
    if topology_issues:
        failures.append("required_topology_mismatch")
    if arc_issues:
        failures.append("arc_geometry_mismatch")
    if annular_sector_issues:
        failures.append("annular_sector_geometry_mismatch")
    if annotation_occlusion_issues:
        failures.append("annotation_occlusion_contract_mismatch")
    return {
        "file": str(path),
        "format": "svg",
        "pass": not failures,
        "failures": failures,
        "counts": {"text": len(texts), "image": len(images), "ids": len(ids)},
        "font_family_issues": font_issues,
        "font_size_issues": size_issues,
        "stroke_width_issues": stroke_issues,
        "remote_images": remote_images,
        "external_references": external_references,
        "missing_source_images": missing_source_images,
        "event_handlers": event_handlers,
        "foreign_object_count": len(foreign_objects),
        "expected_text_count": contract.expected_text_count,
        "missing_required_ids": missing_required_ids,
        "text_content_issues": text_content_issues,
        "text_format_issues": text_format_issues,
        "physical_size_issues": physical_size_issues,
        "atomic_raster_issues": atomic_raster_issues,
        "atomic_raster_contract_required": contract.require_atomic_rasters,
        "raster_contract_issues": raster_contract_issues,
        "zero_raster_contract_required": contract.require_no_raster,
        "path_data_issues": path_data_issues,
        "gradient_reference_issues": gradient_reference_issues,
        "text_path_issues": text_path_issues,
        "element_type_issues": element_type_issues,
        "topology_issues": topology_issues,
        "arc_issues": arc_issues,
        "annular_sector_issues": annular_sector_issues,
        "annotation_occlusion_issues": annotation_occlusion_issues,
        "physical_size": {"width": root.attrib.get("width"), "height": root.attrib.get("height")},
    }


def content_operators(owner, reader) -> list[bytes]:
    from pypdf.generic import ContentStream

    if hasattr(owner, "get_contents"):
        content = owner.get_contents()
    else:
        content = ContentStream(owner, reader)
    operations = content.operations if content is not None else []
    return [operator for _, operator in operations]


def resource_dictionary(owner) -> dict:
    resources = owner.get("/Resources") or {}
    return resources.get_object() if hasattr(resources, "get_object") else resources


def resource_font_names(resources: dict) -> set[str]:
    names = set()
    for font_ref in (resources.get("/Font") or {}).values():
        name = font_ref.get_object().get("/BaseFont")
        if name:
            names.add(str(name))
    return names


def form_xobjects(resources: dict) -> list:
    objects = [reference.get_object() for reference in (resources.get("/XObject") or {}).values()]
    return [item for item in objects if item.get("/Subtype") == "/Form"]


def inspect_pdf_owner(owner, reader, visited: set[int]) -> tuple[bool, set[str]]:
    identity = getattr(owner, "indirect_reference", None)
    object_id = getattr(identity, "idnum", id(owner))
    if object_id in visited:
        return False, set()
    visited.add(object_id)
    operators = content_operators(owner, reader)
    show_text = {b"Tj", b"TJ", b"'", b'"'}
    has_text = b"BT" in operators and any(operator in show_text for operator in operators)
    resources = resource_dictionary(owner)
    names = resource_font_names(resources)
    for xobject in form_xobjects(resources):
        child_text, child_fonts = inspect_pdf_owner(xobject, reader, visited)
        has_text = has_text or child_text
        names.update(child_fonts)
    return has_text, names


def normalized_compact(value: str) -> str:
    return "".join(value.split()).lower()


def audit_pdf(
    path: Path,
    expected_text: tuple[str, ...] = (),
    expected_font_family: str | None = None,
) -> dict:
    from pypdf import PdfReader

    reader = PdfReader(path)
    text_operator_pages = []
    fonts = set()
    extracted_pages = []
    for page_index, page in enumerate(reader.pages, start=1):
        has_text, page_font_names = inspect_pdf_owner(page, reader, set())
        if has_text:
            text_operator_pages.append(page_index)
        fonts.update(page_font_names)
        extracted_pages.append(page.extract_text() or "")
    extracted_text = "\n".join(extracted_pages)
    compact_text = normalized_compact(extracted_text)
    missing_expected_text = [value for value in expected_text if normalized_compact(value) not in compact_text]
    normalized_fonts = normalized_compact(" ".join(fonts))
    font_match = not expected_font_family or normalized_compact(expected_font_family) in normalized_fonts
    failures = []
    if not text_operator_pages:
        failures.append("no_live_text_operators")
    if not fonts:
        failures.append("no_font_resources")
    if missing_expected_text:
        failures.append("expected_pdf_text_missing")
    if not font_match:
        failures.append("expected_pdf_font_missing")
    return {
        "file": str(path),
        "format": "pdf",
        "pass": not failures,
        "failures": failures,
        "page_count": len(reader.pages),
        "text_operator_pages": text_operator_pages,
        "font_resources": sorted(fonts),
        "extracted_text": extracted_text,
        "missing_expected_text": missing_expected_text,
        "expected_font_family": expected_font_family,
        "note": "PDF structural checks do not replace reopening representative text in Illustrator.",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit SVG/PDF evidence for editable publication figures.")
    parser.add_argument("input_file", type=lambda raw: workspace_path(raw, must_exist=True))
    parser.add_argument("--font-family", default="Times New Roman")
    parser.add_argument("--font-size-pt", type=float, default=8.5)
    parser.add_argument("--json-out", type=workspace_path)
    parser.add_argument("--expected-text-count", type=int)
    parser.add_argument("--stroke-id-prefix")
    parser.add_argument("--required-stroke-mm", type=float)
    parser.add_argument("--recipe", type=lambda raw: workspace_path(raw, must_exist=True))
    parser.add_argument("--force", action="store_true", help="Replace the JSON audit output explicitly.")
    return parser.parse_args()


def audit_input(args: argparse.Namespace) -> dict:
    path = args.input_file
    if path.suffix.lower() == ".svg":
        if args.recipe:
            recipe = json.loads(args.recipe.read_text(encoding="utf-8"))
            contract = contract_from_recipe(recipe)
        else:
            contract = SvgAuditContract(
                font_family=args.font_family,
                font_size_pt=args.font_size_pt,
                expected_text_count=args.expected_text_count,
                stroke_id_prefix=args.stroke_id_prefix,
                required_stroke_mm=args.required_stroke_mm,
            )
        return audit_svg(path, contract)
    if path.suffix.lower() == ".pdf":
        if args.recipe:
            recipe = json.loads(args.recipe.read_text(encoding="utf-8"))
            contract = contract_from_recipe(recipe)
            expected = tuple(value for _, value in contract.expected_text)
            return audit_pdf(path, expected, contract.font_family)
        return audit_pdf(path, expected_font_family=args.font_family)
    raise SystemExit("Only SVG and PDF files are supported")


def write_json_output(output: Path, payload: str, force: bool) -> None:
    if output.exists() and not force:
        raise FileExistsError(f"Audit output already exists; choose a new name or pass --force: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="\n", suffix=".json", dir=output.parent, delete=False
    )
    temporary = Path(handle.name)
    try:
        with handle:
            handle.write(payload + "\n")
        os.replace(temporary, output)
    finally:
        if temporary.exists():
            temporary.unlink()


def main() -> None:
    args = parse_args()
    result = audit_input(args)
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    print(payload)
    if args.json_out:
        write_json_output(args.json_out, payload, args.force)
    if not result["pass"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
