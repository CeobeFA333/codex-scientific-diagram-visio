#!/usr/bin/env python3
"""Export an Illustrator-friendly SVG as an editable draw.io mxGraphModel.

The adapter is intentionally conservative. It supports the primitive subset
used by the scientific schematic fixtures and refuses unsupported SVG features
before writing any output. It does not invoke draw.io or Scientific Illustrator.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import os
import re
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
SUPPORTED = {"g", "rect", "ellipse", "line", "polyline", "polygon", "path", "text", "image"}
IGNORED_ROOT = {"title", "metadata", "style"}
FONT_FAMILY = "Times New Roman"
FONT_SIZE_PT = 8.5
PT_PER_MM = 72.0 / 25.4
NUMBER_RE = re.compile(r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")
PATH_TOKEN_RE = re.compile(r"[MLHVZmlhvz]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")
DATA_IMAGE_RE = re.compile(
    r"data:(image/(?:png|jpeg|gif|webp|svg\+xml));base64,([A-Za-z0-9+/=\s]+)", re.IGNORECASE
)


class AdapterError(ValueError):
    """Raised when the source cannot be represented without silent loss."""


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def number(value: str | None, field: str) -> float:
    if value is None or not NUMBER_RE.fullmatch(value.strip()):
        raise AdapterError(f"Unsupported or missing numeric {field}: {value!r}")
    result = float(value)
    if not math.isfinite(result):
        raise AdapterError(f"Non-finite numeric {field}: {value!r}")
    return result


def points(value: str | None, field: str) -> list[tuple[float, float]]:
    if not value:
        raise AdapterError(f"Missing {field}")
    values = [float(token) for token in NUMBER_RE.findall(value)]
    residual = NUMBER_RE.sub("", value).strip(" ,\t\r\n")
    if residual or len(values) < 4 or len(values) % 2:
        raise AdapterError(f"Unsupported {field}: {value!r}")
    return list(zip(values[0::2], values[1::2]))


def style_map(element: ET.Element) -> dict[str, str]:
    result: dict[str, str] = {}
    inline = element.get("style", "")
    for declaration in inline.split(";"):
        if ":" in declaration:
            key, value = declaration.split(":", 1)
            result[key.strip()] = value.strip()
    for key in (
        "fill", "stroke", "stroke-width", "stroke-dasharray", "font-weight",
        "font-style", "text-anchor", "opacity", "fill-opacity", "stroke-opacity",
    ):
        if element.get(key) is not None:
            result[key] = element.get(key, "")
    return result


def color(value: str | None, default: str) -> str:
    if value is None or value == "":
        return default
    if value == "none":
        return "none"
    if re.fullmatch(r"#[0-9a-fA-F]{3}([0-9a-fA-F]{3})?", value):
        if len(value) == 4:
            return "#" + "".join(character * 2 for character in value[1:])
        return value.lower()
    raise AdapterError(f"Unsupported color syntax: {value!r}")


def safe_id(svg_id: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_.-]+", "-", svg_id).strip("-")
    if not normalized:
        raise AdapterError(f"SVG id cannot form a stable draw.io id: {svg_id!r}")
    return f"cell-{normalized}"


def drawio_image_value(href: str | None, image_id: str) -> str:
    """Validate an SVG data URI and normalize it to draw.io's embedded-image form."""
    if not href:
        raise AdapterError(f"Image {image_id} is missing an embedded data URI")
    match = DATA_IMAGE_RE.fullmatch(href.strip())
    if not match:
        raise AdapterError(f"Image {image_id} must use a supported base64 data:image URI")
    mime = match.group(1).lower()
    payload = re.sub(r"\s+", "", match.group(2))
    try:
        base64.b64decode(payload, validate=True)
    except (ValueError, base64.binascii.Error) as error:
        raise AdapterError(f"Image {image_id} has invalid base64 payload") from error
    # mxGraph style declarations use semicolons as separators. diagrams.net stores
    # embedded base64 images as data:<mime>,<payload>, without the URI ;base64 token.
    return f"data:{mime},{payload}"


def parse_length_mm(value: str | None, field: str) -> float:
    if value is None:
        raise AdapterError(f"Missing physical SVG {field}")
    match = re.fullmatch(r"\s*([-+]?(?:\d*\.\d+|\d+\.?))mm\s*", value)
    if not match:
        raise AdapterError(f"SVG {field} must be expressed in mm: {value!r}")
    result = float(match.group(1))
    if result <= 0:
        raise AdapterError(f"SVG {field} must be positive")
    return result


@dataclass(frozen=True)
class Canvas:
    min_x: float
    min_y: float
    width_units: float
    height_units: float
    width_pt: float
    height_pt: float
    scale: float

    def x(self, value: float) -> float:
        return (value - self.min_x) * self.scale

    def y(self, value: float) -> float:
        return (value - self.min_y) * self.scale

    def length(self, value: float) -> float:
        return value * self.scale


def canvas_from_svg(root: ET.Element, recipe: dict | None) -> Canvas:
    view_box = [float(token) for token in NUMBER_RE.findall(root.get("viewBox", ""))]
    if len(view_box) != 4 or view_box[2] <= 0 or view_box[3] <= 0:
        raise AdapterError("SVG requires a positive four-number viewBox")
    width_mm = parse_length_mm(root.get("width"), "width")
    height_mm = parse_length_mm(root.get("height"), "height")
    scale_x = width_mm * PT_PER_MM / view_box[2]
    scale_y = height_mm * PT_PER_MM / view_box[3]
    if not math.isclose(scale_x, scale_y, rel_tol=1e-6, abs_tol=1e-9):
        raise AdapterError("Non-uniform physical SVG scaling is not supported")
    if recipe:
        recipe_canvas = recipe.get("canvas", {})
        for field, actual in (("width_units", view_box[2]), ("height_units", view_box[3])):
            if field in recipe_canvas and not math.isclose(float(recipe_canvas[field]), actual, rel_tol=0, abs_tol=1e-6):
                raise AdapterError(f"Recipe canvas {field} does not match SVG viewBox")
        for field, actual in (("width_mm", width_mm), ("height_mm", height_mm)):
            if field in recipe_canvas and not math.isclose(float(recipe_canvas[field]), actual, rel_tol=0, abs_tol=1e-6):
                raise AdapterError(f"Recipe canvas {field} does not match SVG physical size")
        typography = recipe.get("typography", {})
        if typography.get("font_family", FONT_FAMILY) != FONT_FAMILY:
            raise AdapterError("draw.io backend requires Times New Roman")
        if not math.isclose(float(typography.get("size_pt", FONT_SIZE_PT)), FONT_SIZE_PT, abs_tol=1e-9):
            raise AdapterError("draw.io backend requires 8.5 pt live text")
    return Canvas(
        min_x=view_box[0], min_y=view_box[1], width_units=view_box[2], height_units=view_box[3],
        width_pt=width_mm * PT_PER_MM, height_pt=height_mm * PT_PER_MM, scale=scale_x,
    )


def scan_security_and_ids(root: ET.Element) -> tuple[dict[str, ET.Element], Counter]:
    identifiers: dict[str, ET.Element] = {}
    counts: Counter = Counter()
    for element in root.iter():
        tag = local_name(element.tag)
        counts[tag] += 1
        if tag == "foreignObject":
            raise AdapterError("foreignObject is forbidden")
        for raw_key, raw_value in element.attrib.items():
            key = local_name(raw_key).lower()
            value = raw_value.strip()
            if key.startswith("on"):
                raise AdapterError(f"Event handler attribute is forbidden: {raw_key}")
            if "url(" in value.lower():
                raise AdapterError(f"URL paint/reference is unsupported: {raw_key}={value!r}")
            if key == "href" and tag != "image":
                raise AdapterError(f"Only image data URIs are supported: {tag} href")
        if tag in SUPPORTED:
            identifier = element.get("id")
            if not identifier:
                raise AdapterError(f"Every drawable/group element requires a stable SVG id: <{tag}>")
            if identifier in identifiers:
                raise AdapterError(f"Duplicate SVG id: {identifier}")
            identifiers[identifier] = element
    return identifiers, counts


def path_points(data: str | None) -> list[tuple[float, float]]:
    if not data:
        raise AdapterError("Path is missing d data")
    tokens = PATH_TOKEN_RE.findall(data)
    residual = PATH_TOKEN_RE.sub("", data).strip(" ,\t\r\n")
    if residual:
        raise AdapterError(f"Unsupported path token(s): {residual!r}")
    output: list[tuple[float, float]] = []
    cursor = (0.0, 0.0)
    start = cursor
    command = ""
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.isalpha():
            command = token
            index += 1
            if command in "Zz":
                output.append(start)
                cursor = start
                continue
        if command not in "MmLlHhVv":
            raise AdapterError(f"Unsupported path command {command!r}; only M/L/H/V/Z are accepted")
        relative = command.islower()
        upper = command.upper()
        if upper in {"M", "L"}:
            if index + 1 >= len(tokens) or tokens[index].isalpha() or tokens[index + 1].isalpha():
                raise AdapterError(f"Path command {command} has incomplete coordinates")
            x, y = float(tokens[index]), float(tokens[index + 1])
            index += 2
            if relative:
                x += cursor[0]
                y += cursor[1]
            cursor = (x, y)
            if upper == "M":
                start = cursor
                command = "l" if relative else "L"
            output.append(cursor)
        elif upper == "H":
            if index >= len(tokens) or tokens[index].isalpha():
                raise AdapterError(f"Path command {command} has incomplete coordinates")
            x = float(tokens[index]) + (cursor[0] if relative else 0)
            index += 1
            cursor = (x, cursor[1])
            output.append(cursor)
        else:
            if index >= len(tokens) or tokens[index].isalpha():
                raise AdapterError(f"Path command {command} has incomplete coordinates")
            y = float(tokens[index]) + (cursor[1] if relative else 0)
            index += 1
            cursor = (cursor[0], y)
            output.append(cursor)
    if len(output) < 2:
        raise AdapterError("Path must contain at least two points")
    return output


def geometry(parent: ET.Element, *, x: float, y: float, width: float, height: float, relative: bool = False) -> ET.Element:
    attributes = {
        "x": f"{x:.4f}", "y": f"{y:.4f}", "width": f"{width:.4f}",
        "height": f"{height:.4f}", "as": "geometry",
    }
    if relative:
        attributes["relative"] = "1"
    return ET.SubElement(parent, "mxGeometry", attributes)


def base_style(element: ET.Element, canvas: Canvas) -> tuple[str, str, float, bool]:
    source = style_map(element)
    fill = color(source.get("fill"), "none")
    stroke = color(source.get("stroke"), "none")
    stroke_width = canvas.length(number(source.get("stroke-width", "1"), "stroke-width"))
    dashed = source.get("stroke-dasharray", "none") != "none"
    return fill, stroke, stroke_width, dashed


def shape_style(prefix: str, element: ET.Element, canvas: Canvas) -> str:
    fill, stroke, stroke_width, dashed = base_style(element, canvas)
    parts = [prefix, "html=0", "whiteSpace=wrap"]
    parts.append(f"fillColor={fill if fill != 'none' else 'none'}")
    parts.append(f"strokeColor={stroke if stroke != 'none' else 'none'}")
    parts.append(f"strokeWidth={stroke_width:.4f}")
    if dashed:
        parts.append("dashed=1")
    return ";".join(parts) + ";"


def edge_style(element: ET.Element, canvas: Canvas) -> str:
    _, stroke, stroke_width, dashed = base_style(element, canvas)
    parts = [
        "edgeStyle=none", "html=0", "rounded=0", "orthogonalLoop=0", "jettySize=auto",
        "startArrow=none", "endArrow=none", f"strokeColor={stroke if stroke != 'none' else 'none'}",
        f"strokeWidth={stroke_width:.4f}",
    ]
    if dashed:
        parts.append("dashed=1")
    return ";".join(parts) + ";"


def direction_for_triangle(raw_points: list[tuple[float, float]]) -> str:
    xs = [point[0] for point in raw_points]
    ys = [point[1] for point in raw_points]
    width, height = max(xs) - min(xs), max(ys) - min(ys)
    centroid = (sum(xs) / 3, sum(ys) / 3)
    tip = max(raw_points, key=lambda point: math.hypot(point[0] - centroid[0], point[1] - centroid[1]))
    if width >= height:
        return "east" if tip[0] >= centroid[0] else "west"
    return "south" if tip[1] >= centroid[1] else "north"


def add_edge_geometry(cell: ET.Element, converted: list[tuple[float, float]]) -> None:
    edge_geometry = ET.SubElement(cell, "mxGeometry", {"relative": "1", "as": "geometry"})
    ET.SubElement(edge_geometry, "mxPoint", {"x": f"{converted[0][0]:.4f}", "y": f"{converted[0][1]:.4f}", "as": "sourcePoint"})
    ET.SubElement(edge_geometry, "mxPoint", {"x": f"{converted[-1][0]:.4f}", "y": f"{converted[-1][1]:.4f}", "as": "targetPoint"})
    if len(converted) > 2:
        array = ET.SubElement(edge_geometry, "Array", {"as": "points"})
        for x, y in converted[1:-1]:
            ET.SubElement(array, "mxPoint", {"x": f"{x:.4f}", "y": f"{y:.4f}"})


def text_style(element: ET.Element) -> str:
    source = style_map(element)
    anchor = source.get("text-anchor", element.get("text-anchor", "start"))
    alignment = {"start": "left", "middle": "center", "end": "right"}.get(anchor)
    if alignment is None:
        raise AdapterError(f"Unsupported text-anchor: {anchor!r}")
    class_names = set(element.get("class", "").split())
    bold = source.get("font-weight") in {"bold", "600", "700", "800", "900"} or "formula" in class_names
    italic = source.get("font-style") == "italic" or "formula" in class_names
    font_style = (1 if bold else 0) + (2 if italic else 0)
    fill = color(source.get("fill"), "#171717")
    return (
        "text;html=0;whiteSpace=wrap;overflow=visible;resizable=0;points=[];"
        f"align={alignment};verticalAlign=middle;fontFamily={FONT_FAMILY};fontSize={FONT_SIZE_PT};"
        f"fontColor={fill};fontStyle={font_style};strokeColor=none;fillColor=none;"
    )


def plain_text(element: ET.Element) -> str:
    value = "".join(element.itertext())
    value = re.sub(r"\s+", " ", value).strip()
    if not value:
        raise AdapterError(f"Empty live text: {element.get('id')}")
    return value


def semantic_connections(recipe: dict | None) -> dict[str, dict]:
    if not recipe:
        return {}
    return {str(item["id"]): item for item in recipe.get("connections", []) if "id" in item}


def build_model(svg_path: Path, recipe_path: Path | None = None) -> tuple[ET.Element, dict]:
    try:
        svg_root = ET.parse(svg_path).getroot()
    except ET.ParseError as error:
        raise AdapterError(f"Invalid SVG XML: {error}") from error
    if local_name(svg_root.tag) != "svg":
        raise AdapterError("Input root must be svg")
    recipe = json.loads(recipe_path.read_text(encoding="utf-8")) if recipe_path else None
    canvas = canvas_from_svg(svg_root, recipe)
    source_ids, source_counts = scan_security_and_ids(svg_root)
    if recipe and recipe.get("contract", {}).get("require_zero_rasters"):
        if source_counts["image"]:
            raise AdapterError("Recipe requires zero rasters but SVG contains image elements")
    required_connections = set(recipe.get("contract", {}).get("required_connection_ids", [])) if recipe else set()
    missing_connections = sorted(required_connections - set(source_ids))
    if missing_connections:
        raise AdapterError(f"Recipe-required connection IDs are missing: {missing_connections}")

    model = ET.Element(
        "mxGraphModel",
        {
            "dx": "0", "dy": "0", "grid": "1", "gridSize": "10", "guides": "1",
            "tooltips": "1", "connect": "1", "arrows": "1", "fold": "1", "page": "1",
            "pageScale": "1", "pageWidth": f"{canvas.width_pt:.4f}",
            "pageHeight": f"{canvas.height_pt:.4f}", "math": "0", "shadow": "0",
        },
    )
    mx_root = ET.SubElement(model, "root")
    ET.SubElement(mx_root, "mxCell", {"id": "0"})
    ET.SubElement(mx_root, "mxCell", {"id": "layer-background", "value": "Background", "parent": "0"})
    ET.SubElement(mx_root, "mxCell", {"id": "layer-content", "value": "Scientific editable content", "parent": "0"})

    used_cell_ids = {"0", "layer-background", "layer-content"}
    mapped: dict[str, str] = {}
    mx_counts: Counter = Counter()
    semantics = semantic_connections(recipe)
    for connection_id, connection in semantics.items():
        endpoint_ids = (str(connection.get("from", "")), str(connection.get("to", "")))
        if not all(endpoint_ids):
            raise AdapterError(f"Recipe connection {connection_id} requires non-empty from/to endpoints")
        missing_endpoints = sorted(endpoint for endpoint in endpoint_ids if endpoint not in source_ids)
        if missing_endpoints:
            raise AdapterError(
                f"Recipe connection {connection_id} references missing endpoint(s): {missing_endpoints}"
            )

    def register(element: ET.Element) -> str:
        svg_id = element.get("id", "")
        cell_id = safe_id(svg_id)
        if cell_id in used_cell_ids:
            raise AdapterError(f"Stable draw.io cell id collision: {cell_id}")
        used_cell_ids.add(cell_id)
        mapped[svg_id] = cell_id
        return cell_id

    def convert(element: ET.Element, parent_id: str) -> None:
        tag = local_name(element.tag)
        if tag not in SUPPORTED:
            raise AdapterError(f"Unsupported SVG element: <{tag}>")
        cell_id = register(element)
        if tag == "g":
            cell = ET.SubElement(
                mx_root, "mxCell",
                {
                    "id": cell_id, "value": "", "style": "group;html=0;", "vertex": "1",
                    "connectable": "0", "parent": parent_id,
                    "data-svg-id": element.get("id", ""),
                    "data-label": element.get("aria-label", ""),
                },
            )
            geometry(cell, x=0, y=0, width=canvas.width_pt, height=canvas.height_pt)
            mx_counts["group"] += 1
            for child in element:
                child_tag = local_name(child.tag)
                if child_tag in SUPPORTED:
                    convert(child, cell_id)
                elif child_tag not in IGNORED_ROOT:
                    raise AdapterError(f"Unsupported child <{child_tag}> inside group {element.get('id')}")
            return

        data_attributes = {"data-svg-id": element.get("id", "")}
        semantic = semantics.get(element.get("id", ""))
        if semantic:
            data_attributes.update(
                {
                    "data-source-svg-id": str(semantic.get("from", "")),
                    "data-target-svg-id": str(semantic.get("to", "")),
                    "data-meaning": str(semantic.get("meaning", "")),
                }
            )
        if tag == "text":
            value = plain_text(element)
            x = canvas.x(number(element.get("x"), "text x"))
            baseline = canvas.y(number(element.get("y"), "text y"))
            width = max(12.0, len(value) * FONT_SIZE_PT * 0.58)
            height = FONT_SIZE_PT * 1.3
            anchor = element.get("text-anchor", "start")
            left = x if anchor == "start" else x - width / 2 if anchor == "middle" else x - width
            cell = ET.SubElement(
                mx_root, "mxCell",
                {"id": cell_id, "value": value, "style": text_style(element), "vertex": "1", "parent": parent_id, **data_attributes},
            )
            geometry(cell, x=left, y=baseline - height, width=width, height=height)
            mx_counts["text_vertex"] += 1
            return
        if tag in {"line", "polyline", "path"}:
            if tag == "line":
                raw = [
                    (number(element.get("x1"), "line x1"), number(element.get("y1"), "line y1")),
                    (number(element.get("x2"), "line x2"), number(element.get("y2"), "line y2")),
                ]
            elif tag == "polyline":
                raw = points(element.get("points"), "polyline points")
            else:
                raw = path_points(element.get("d"))
            converted = [(canvas.x(x), canvas.y(y)) for x, y in raw]
            edge_attributes = {
                "id": cell_id, "value": "", "style": edge_style(element, canvas),
                "edge": "1", "parent": parent_id, **data_attributes,
            }
            if semantic:
                edge_attributes["source"] = safe_id(str(semantic["from"]))
                edge_attributes["target"] = safe_id(str(semantic["to"]))
            cell = ET.SubElement(
                mx_root, "mxCell",
                edge_attributes,
            )
            add_edge_geometry(cell, converted)
            mx_counts["edge"] += 1
            return
        if tag == "rect":
            x = canvas.x(number(element.get("x", "0"), "rect x"))
            y = canvas.y(number(element.get("y", "0"), "rect y"))
            width = canvas.length(number(element.get("width"), "rect width"))
            height = canvas.length(number(element.get("height"), "rect height"))
            rounded = number(element.get("rx", "0"), "rect rx") > 0
            prefix = "rounded=1;arcSize=12" if rounded else "rounded=0"
            style = shape_style(prefix, element, canvas)
        elif tag == "ellipse":
            rx = number(element.get("rx"), "ellipse rx")
            ry = number(element.get("ry"), "ellipse ry")
            x = canvas.x(number(element.get("cx"), "ellipse cx") - rx)
            y = canvas.y(number(element.get("cy"), "ellipse cy") - ry)
            width, height = canvas.length(2 * rx), canvas.length(2 * ry)
            style = shape_style("ellipse", element, canvas)
        elif tag == "polygon":
            raw = points(element.get("points"), "polygon points")
            xs, ys = [point[0] for point in raw], [point[1] for point in raw]
            x, y = canvas.x(min(xs)), canvas.y(min(ys))
            width, height = canvas.length(max(xs) - min(xs)), canvas.length(max(ys) - min(ys))
            if len(raw) == 3:
                prefix = f"triangle;direction={direction_for_triangle(raw)}"
            elif len(raw) == 4:
                prefix = "shape=parallelogram;perimeter=parallelogramPerimeter"
            else:
                raise AdapterError(f"Only triangle and quadrilateral polygons are supported: {element.get('id')}")
            style = shape_style(prefix, element, canvas)
        elif tag == "image":
            href = element.get("href") or element.get(f"{{{XLINK_NS}}}href")
            embedded_image = drawio_image_value(href, element.get("id", ""))
            x = canvas.x(number(element.get("x", "0"), "image x"))
            y = canvas.y(number(element.get("y", "0"), "image y"))
            width = canvas.length(number(element.get("width"), "image width"))
            height = canvas.length(number(element.get("height"), "image height"))
            style = f"shape=image;html=0;imageAspect=0;aspect=fixed;image={embedded_image};"
        else:
            raise AdapterError(f"Unsupported SVG element: <{tag}>")
        if width <= 0 or height <= 0:
            raise AdapterError(f"Non-positive geometry for {element.get('id')}")
        cell = ET.SubElement(
            mx_root, "mxCell",
            {"id": cell_id, "value": "", "style": style, "vertex": "1", "parent": parent_id, **data_attributes},
        )
        geometry(cell, x=x, y=y, width=width, height=height)
        mx_counts["image_vertex" if tag == "image" else "shape_vertex"] += 1

    for child in svg_root:
        tag = local_name(child.tag)
        if tag in IGNORED_ROOT:
            continue
        if tag not in SUPPORTED:
            raise AdapterError(f"Unsupported top-level SVG element: <{tag}>")
        target_layer = "layer-background" if child.get("id") == "page-background" else "layer-content"
        convert(child, target_layer)

    if set(mapped) != set(source_ids):
        missing = sorted(set(source_ids) - set(mapped))
        raise AdapterError(f"Not every source object was mapped: {missing}")
    details = {
        "canvas": {
            "width_pt": canvas.width_pt, "height_pt": canvas.height_pt,
            "source_width_units": canvas.width_units, "source_height_units": canvas.height_units,
        },
        "source_counts": dict(sorted(source_counts.items())),
        "mx_counts": dict(sorted(mx_counts.items())),
        "source_object_count": len(source_ids),
        "mapped_object_count": len(mapped),
        "stable_id_map": dict(sorted(mapped.items())),
    }
    return model, details


def serialize_xml(root: ET.Element) -> bytes:
    if hasattr(ET, "indent"):
        ET.indent(root, space="  ")
    else:
        indent_xml_compat(root)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True, short_empty_elements=True) + b"\n"


def is_blank_xml_whitespace(value: str | None) -> bool:
    return value is None or not value.strip()


def indent_xml_compat(element: ET.Element, level: int = 0) -> None:
    """Match ElementTree.indent for supported Python 3.8 runtimes."""
    indentation = "\n" + level * "  "
    child_indentation = "\n" + (level + 1) * "  "
    if len(element):
        if is_blank_xml_whitespace(element.text):
            element.text = child_indentation
        for child in element:
            indent_xml_compat(child, level + 1)
            if is_blank_xml_whitespace(child.tail):
                child.tail = child_indentation
        if is_blank_xml_whitespace(element[-1].tail):
            element[-1].tail = indentation
    elif level and is_blank_xml_whitespace(element.tail):
        element.tail = indentation


def audit_model(model: ET.Element, details: dict) -> dict:
    failures: list[str] = []
    cells = model.findall("./root/mxCell")
    ids = [cell.get("id", "") for cell in cells]
    if len(ids) != len(set(ids)):
        failures.append("duplicate_mxcell_ids")
    text_cells = [cell for cell in cells if cell.get("vertex") == "1" and cell.get("style", "").startswith("text;")]
    edge_cells = [cell for cell in cells if cell.get("edge") == "1"]
    vertex_cells = [cell for cell in cells if cell.get("vertex") == "1"]
    image_cells = [cell for cell in vertex_cells if "shape=image" in cell.get("style", "")]
    for cell in vertex_cells + edge_cells:
        if "html=0" not in cell.get("style", ""):
            failures.append(f"html_not_disabled:{cell.get('id')}")
    for cell in text_cells:
        style = cell.get("style", "")
        if f"fontFamily={FONT_FAMILY}" not in style or f"fontSize={FONT_SIZE_PT}" not in style:
            failures.append(f"typography_contract:{cell.get('id')}")
        if "<" in cell.get("value", "") or ">" in cell.get("value", ""):
            failures.append(f"non_plain_text:{cell.get('id')}")
    for cell in image_cells:
        style = cell.get("style", "")
        if "image=data:image/" not in style:
            failures.append(f"non_embedded_image:{cell.get('id')}")
    serialized = ET.tostring(model, encoding="unicode")
    if "foreignObject" in serialized or "http://" in serialized or "https://" in serialized or "file://" in serialized:
        failures.append("forbidden_external_or_foreign_content")
    if details["source_object_count"] != details["mapped_object_count"]:
        failures.append("source_mapping_incomplete")
    return {
        "pass": not failures,
        "failures": failures,
        "root": model.tag,
        "counts": {
            "mx_cells": len(cells), "vertices": len(vertex_cells), "edges": len(edge_cells),
            "groups": details["mx_counts"].get("group", 0), "text_vertices": len(text_cells),
            "image_vertices": len(image_cells),
        },
        "contracts": {
            "html_disabled": True, "plain_text_only": True,
            "font_family": FONT_FAMILY, "font_size_pt": FONT_SIZE_PT,
            "stable_ids": True, "external_references": 0, "foreign_objects": 0,
        },
        "plugin_execution": {
            "scientific_illustrator_installed_or_invoked": False,
            "note": "This audit validates mxGraphModel structure only; the Scientific Illustrator/draw.io backend was not installed or called.",
        },
    }


def atomic_write(path: Path, payload: bytes, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(prefix=f".{path.stem}-", suffix=path.suffix, dir=path.parent, delete=False)
    temporary = Path(handle.name)
    try:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
        handle.close()
        os.replace(temporary, path)
    finally:
        if not handle.closed:
            handle.close()
        if temporary.exists():
            temporary.unlink()


def export_scene(
    svg_path: Path,
    output_path: Path,
    *,
    recipe_path: Path | None = None,
    manifest_path: Path | None = None,
    audit_path: Path | None = None,
    overwrite: bool = False,
) -> dict:
    svg_path = svg_path.resolve()
    output_path = output_path.resolve()
    recipe_path = recipe_path.resolve() if recipe_path else None
    manifest_path = (manifest_path or output_path.with_suffix(".manifest.json")).resolve()
    audit_path = (audit_path or output_path.with_suffix(".audit.json")).resolve()
    targets = (output_path, manifest_path, audit_path)
    if len(set(targets)) != 3:
        raise AdapterError("draw.io, manifest and audit outputs must be distinct")
    if not overwrite:
        existing = [str(path) for path in targets if path.exists()]
        if existing:
            raise FileExistsError(f"Refusing to overwrite existing output(s): {existing}")
    model, details = build_model(svg_path, recipe_path)
    drawio_payload = serialize_xml(model)
    audit = audit_model(model, details)
    if not audit["pass"]:
        raise AdapterError(f"Generated mxGraphModel failed audit: {audit['failures']}")
    audit.update(
        {
            "source_svg": str(svg_path), "source_svg_sha256": sha256_file(svg_path),
            "drawio": str(output_path), "drawio_sha256": sha256_bytes(drawio_payload),
        }
    )
    manifest = {
        "format": "drawio-mxGraphModel",
        "adapter": "Scientific Illustrator/draw.io backend staging adapter",
        "source_svg": str(svg_path),
        "source_svg_sha256": sha256_file(svg_path),
        "recipe": str(recipe_path) if recipe_path else None,
        "recipe_sha256": sha256_file(recipe_path) if recipe_path else None,
        "drawio": str(output_path),
        "drawio_sha256": sha256_bytes(drawio_payload),
        "audit": str(audit_path),
        "counts": details,
        "contracts": audit["contracts"],
        "plugin_execution": audit["plugin_execution"],
        "publication_status": "backend-editability-candidate-not-a-publication-approval",
    }
    manifest_payload = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    audit_payload = (json.dumps(audit, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    atomic_write(output_path, drawio_payload, overwrite)
    atomic_write(manifest_path, manifest_payload, overwrite)
    atomic_write(audit_path, audit_payload, overwrite)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("svg", type=Path, help="Illustrator-friendly SVG input")
    parser.add_argument("output", type=Path, help="Uncompressed .drawio mxGraphModel output")
    parser.add_argument("--recipe", type=Path, help="Optional reconstruction recipe")
    parser.add_argument("--manifest-out", type=Path, help="Optional manifest JSON path")
    parser.add_argument("--audit-out", type=Path, help="Optional audit JSON path")
    parser.add_argument("--force", action="store_true", help="Replace all three generated outputs")
    args = parser.parse_args()
    manifest = export_scene(
        args.svg,
        args.output,
        recipe_path=args.recipe,
        manifest_path=args.manifest_out,
        audit_path=args.audit_out,
        overwrite=args.force,
    )
    print(json.dumps(manifest["counts"]["mx_counts"], ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
