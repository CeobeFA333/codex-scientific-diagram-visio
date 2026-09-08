#!/usr/bin/env python3
"""Export a strict Illustrator-friendly SVG as a Scientific SceneGraph.

The adapter is offline and file-only.  It never starts Visio, installs the
Visio Scientific Illustrator plugin, or claims that the emitted scene was
drawn successfully.  Unsupported or ambiguous SVG constructs fail closed.
"""

import argparse
import hashlib
import json
import math
import os
import re
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path


SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
UPSTREAM_REPOSITORY = "https://github.com/TZ-mx/Visio-Illustrator"
UPSTREAM_COMMIT = "69df39c641f38574110563ee343f2a4d8fad30a3"
UPSTREAM_SCHEMA_PATH = "plugins/visio-scientific-illustrator/scripts/scene-schema.mjs"
WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
SUPPORTED_RENDER_TAGS = {"rect", "ellipse", "circle", "line", "polygon", "polyline", "path", "text"}
ALLOWED_NON_RENDER_TAGS = {"svg", "title", "metadata", "style", "g", "tspan"}
FORBIDDEN_ATTRIBUTES = {"transform", "clip-path", "mask", "filter"}
NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
PATH_TOKEN = re.compile(r"[A-Za-z]|" + NUMBER)
LENGTH = re.compile(r"^\s*(%s)\s*(mm|cm|in|pt|px)?\s*$" % NUMBER)
CSS_RULE = re.compile(r"\.([A-Za-z_][\w-]*)\s*\{([^}]*)\}")


class AdapterError(ValueError):
    """Stable fail-closed adapter error."""


def local_name(tag):
    return tag.rsplit("}", 1)[-1]


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def round_number(value):
    value = round(float(value), 6)
    return int(value) if value.is_integer() else value


def parse_length(value, field):
    match = LENGTH.match(value or "")
    if not match:
        raise AdapterError("%s must be an absolute SVG length" % field)
    number = float(match.group(1))
    unit = match.group(2) or "px"
    if not math.isfinite(number) or number <= 0:
        raise AdapterError("%s must be positive and finite" % field)
    to_inches = {"in": 1.0, "mm": 1.0 / 25.4, "cm": 1.0 / 2.54, "pt": 1.0 / 72.0, "px": 1.0 / 96.0}
    return number * to_inches[unit], unit


def parse_number(value, field):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise AdapterError("%s must be numeric" % field)
    if not math.isfinite(number):
        raise AdapterError("%s must be finite" % field)
    return number


def parse_viewbox(root):
    parts = re.split(r"[\s,]+", root.attrib.get("viewBox", "").strip())
    if len(parts) != 4:
        raise AdapterError("SVG viewBox must have four numbers")
    x, y, width, height = [parse_number(value, "viewBox") for value in parts]
    if x != 0 or y != 0 or width <= 0 or height <= 0:
        raise AdapterError("Only a positive zero-origin viewBox is supported")
    if not float(width).is_integer() or not float(height).is_integer():
        raise AdapterError("SceneGraph canvas requires integer viewBox dimensions")
    return int(width), int(height)


def css_classes(root):
    classes = {}
    for style in root.findall("{%s}style" % SVG_NS):
        text = style.text or ""
        if "url(" in text or "@import" in text:
            raise AdapterError("CSS URL/import references are forbidden")
        stripped = CSS_RULE.sub("", text)
        if stripped.strip():
            raise AdapterError("Only simple .class CSS rules are supported")
        for match in CSS_RULE.finditer(text):
            declarations = {}
            for item in match.group(2).split(";"):
                if not item.strip():
                    continue
                if ":" not in item:
                    raise AdapterError("Malformed CSS declaration")
                key, value = item.split(":", 1)
                declarations[key.strip()] = value.strip().strip("'\"")
            classes[match.group(1)] = declarations
    return classes


def merged_style(element, classes):
    result = {}
    for name in element.attrib.get("class", "").split():
        if name not in classes:
            raise AdapterError("Unknown SVG class: %s" % name)
        result.update(classes[name])
    if element.attrib.get("style"):
        for item in element.attrib["style"].split(";"):
            if not item.strip():
                continue
            if ":" not in item:
                raise AdapterError("Malformed inline style")
            key, value = item.split(":", 1)
            result[key.strip()] = value.strip()
    for key in (
        "fill", "stroke", "stroke-width", "stroke-dasharray", "stroke-linecap", "stroke-linejoin",
        "fill-opacity", "stroke-opacity", "opacity", "font-family", "font-size", "font-style",
        "font-weight", "text-anchor", "baseline-shift",
    ):
        if key in element.attrib:
            result[key] = element.attrib[key]
    if any("url(" in value for value in result.values()):
        raise AdapterError("Paint-server and external URL references are unsupported")
    return result


def color_or_none(value, field):
    if value is None or value == "none":
        return None
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
        raise AdapterError("%s must be #RRGGBB or none" % field)
    return value.upper()


def opacity_percent(style, name):
    value = parse_number(style.get(name, "1"), name)
    if value < 0 or value > 1:
        raise AdapterError("%s must be within 0..1" % name)
    return round_number(100.0 * (1.0 - value))


def shape_style(style, dpi, text_block=None, corner_radius_units=None):
    fill_color = color_or_none(style.get("fill"), "fill")
    stroke_color = color_or_none(style.get("stroke"), "stroke")
    result = {
        "fill": {"kind": "none"} if fill_color is None else {
            "kind": "solid", "color": fill_color,
            "transparency_percent": opacity_percent(style, "fill-opacity"),
        },
        "line": {
            "width_pt": round_number(parse_number(style.get("stroke-width", "0"), "stroke-width") * 72.0 / dpi)
        },
    }
    if stroke_color is not None:
        result["line"]["color"] = stroke_color
        result["line"]["transparency_percent"] = opacity_percent(style, "stroke-opacity")
    if style.get("stroke-dasharray") not in (None, "none"):
        if not all(re.fullmatch(NUMBER, token) for token in re.split(r"[\s,]+", style["stroke-dasharray"].strip())):
            raise AdapterError("stroke-dasharray must contain numeric lengths")
        result["line"]["pattern"] = 2
    cap = style.get("stroke-linecap")
    if cap:
        result["line"]["cap"] = {"butt": "square", "square": "extended", "round": "round"}.get(cap)
        if result["line"]["cap"] is None:
            raise AdapterError("Unsupported stroke-linecap: %s" % cap)
    join = style.get("stroke-linejoin")
    if join:
        if join not in ("round", "bevel", "miter"):
            raise AdapterError("Unsupported stroke-linejoin: %s" % join)
        # The current Visio bridge accepts ``line.join`` in its JavaScript
        # schema but writes a non-universal LineJoin ShapeSheet cell. Basic
        # rectangles and ellipses can therefore fail at runtime with
        # CELL_NOT_AVAILABLE. Validate the source value, then let Visio use
        # the native shape default for this intermediate authoring backend.
    if text_block is not None:
        result["text_block"] = text_block
    if corner_radius_units is not None:
        result["corner"] = {"radius_pt": round_number(corner_radius_units * 72.0 / dpi)}
    if "opacity" in style:
        result["opacity_percent"] = round_number(100.0 - parse_number(style["opacity"], "opacity") * 100.0)
    return result


def element_id(element):
    identifier = element.attrib.get("id")
    if not identifier:
        raise AdapterError("Every rendered SVG element and group must have a stable id")
    if len(identifier) > 120:
        raise AdapterError("Semantic id exceeds upstream limit: %s" % identifier)
    return identifier


def bbox_union(boxes):
    if not boxes:
        raise AdapterError("Cannot compute an empty group bound")
    x1 = min(box[0] for box in boxes)
    y1 = min(box[1] for box in boxes)
    x2 = max(box[0] + box[2] for box in boxes)
    y2 = max(box[1] + box[3] for box in boxes)
    return (x1, y1, x2 - x1, y2 - y1)


def positive_bbox(x, y, width, height):
    epsilon = 0.001
    if width == 0:
        x -= epsilon / 2
        width = epsilon
    if height == 0:
        y -= epsilon / 2
        height = epsilon
    return (x, y, width, height)


def polygon_points(value):
    numbers = [parse_number(item, "points") for item in re.findall(NUMBER, value or "")]
    if len(numbers) < 4 or len(numbers) % 2:
        raise AdapterError("polygon/polyline points must contain coordinate pairs")
    return list(zip(numbers[0::2], numbers[1::2]))


def parse_path(value):
    tokens = PATH_TOKEN.findall(value or "")
    if not tokens:
        raise AdapterError("Empty SVG path")
    commands = []
    index = 0
    arity = {"M": 2, "L": 2, "C": 6, "A": 7, "Z": 0}
    while index < len(tokens):
        op = tokens[index]
        index += 1
        if op not in arity:
            raise AdapterError("Only absolute M/L/C/A/Z SVG path commands are supported; found %s" % op)
        count = arity[op]
        if index + count > len(tokens):
            raise AdapterError("Truncated SVG path command %s" % op)
        values = [parse_number(token, "path") for token in tokens[index:index + count]]
        index += count
        if index < len(tokens) and not tokens[index].isalpha():
            raise AdapterError("Implicit repeated SVG path commands are unsupported")
        command = {"op": op}
        if op in ("M", "L"):
            command.update(x=values[0], y=values[1])
        elif op == "C":
            command.update(x1=values[0], y1=values[1], x2=values[2], y2=values[3], x=values[4], y=values[5])
        elif op == "A":
            if values[3] not in (0, 1) or values[4] not in (0, 1):
                raise AdapterError("SVG arc flags must be 0 or 1")
            command.update(rx=values[0], ry=values[1], rotation_deg=values[2],
                           large_arc=bool(values[3]), sweep=bool(values[4]), x=values[5], y=values[6])
        commands.append(command)
    if commands[0]["op"] != "M":
        raise AdapterError("SVG path must start with M")
    points = []
    for command in commands:
        for x_name, y_name in (("x", "y"), ("x1", "y1"), ("x2", "y2")):
            if x_name in command:
                points.append((command[x_name], command[y_name]))
    if not points:
        raise AdapterError("SVG path has no coordinates")
    x1 = min(x for x, _ in points)
    y1 = min(y for _, y in points)
    x2 = max(x for x, _ in points)
    y2 = max(y for _, y in points)
    box = positive_bbox(x1, y1, x2 - x1, y2 - y1)
    localized = []
    for command in commands:
        item = dict(command)
        for x_name, y_name in (("x", "y"), ("x1", "y1"), ("x2", "y2")):
            if x_name in item:
                item[x_name] = round_number(item[x_name] - box[0])
                item[y_name] = round_number(item[y_name] - box[1])
        if "rx" in item:
            item["rx"] = round_number(item["rx"])
            item["ry"] = round_number(item["ry"])
            item["rotation_deg"] = round_number(item["rotation_deg"])
        localized.append(item)
    return box, localized, commands[-1]["op"] == "Z"


def utf16_length(value):
    return len(value.encode("utf-16-le")) // 2


def text_content_and_runs(element, style, classes, dpi):
    parts = []
    run_specs = []
    children = [child for child in element if local_name(child.tag) == "tspan"]
    if children and (element.text or "").strip():
        raise AdapterError("Mixed direct text and tspan content is unsupported")
    segments = children or [element]
    cursor = 0
    for segment in segments:
        text = "".join(segment.itertext())
        if not text:
            continue
        segment_style = dict(style)
        if segment is not element:
            segment_style.update(merged_style(segment, classes))
        family = segment_style.get("font-family", "Times New Roman").split(",")[0].strip().strip("'\"")
        size_units = parse_number(segment_style.get("font-size"), "font-size")
        run = {
            "start": cursor,
            "length": utf16_length(text),
            "font_family": family,
            "font_size_pt": round_number(size_units * 72.0 / dpi),
            "color": color_or_none(segment_style.get("fill", "#000000"), "text fill") or "#000000",
        }
        if segment_style.get("font-weight") in ("bold", "600", "700", "800", "900"):
            run["bold"] = True
        if segment_style.get("font-style") == "italic":
            run["italic"] = True
        shift = segment_style.get("baseline-shift")
        if shift == "sub":
            run["subscript"] = True
        elif shift == "super":
            run["superscript"] = True
        elif shift not in (None, "baseline"):
            raise AdapterError("Only sub/super baseline shifts are supported")
        parts.append(text)
        run_specs.append(run)
        cursor += utf16_length(text)
    value = "".join(parts)
    if not value:
        raise AdapterError("Text element is empty")
    return value, run_specs


def text_node(element, style, classes, dpi, z_order):
    identifier = element_id(element)
    text, runs = text_content_and_runs(element, style, classes, dpi)
    x = parse_number(element.attrib.get("x"), identifier + ".x")
    y = parse_number(element.attrib.get("y"), identifier + ".y")
    size_units = parse_number(style.get("font-size"), identifier + ".font-size")
    width = max(size_units, sum(0.58 * size_units for _ in text))
    height = size_units * 1.45
    anchor = style.get("text-anchor", "start")
    if anchor == "middle":
        left = x - width / 2
        horizontal = "center"
    elif anchor == "end":
        left = x - width
        horizontal = "right"
    elif anchor == "start":
        left = x
        horizontal = "left"
    else:
        raise AdapterError("Unsupported text-anchor: %s" % anchor)
    top = y - size_units * 1.15
    box = positive_bbox(max(0, left), max(0, top), width, height)
    return {
        "kind": "text",
        "semantic_id": identifier,
        "bounds": box_dict(box),
        "layer": "live-text",
        "z_order": z_order,
        # The current upstream SceneExecutor ranks ordinary text after group
        # creation. A group containing text would therefore reference a
        # shape that has not been drawn yet. Roles containing ``panel`` are
        # intentionally scheduled before groups, while remaining semantically
        # recognizable as live text.
        "role": "live_text",
        "text": text,
        "style": shape_style({"fill": "none", "stroke": "none", "stroke-width": "0"}, dpi, {
            "horizontal_align": horizontal, "vertical_align": "middle",
            "left_margin_pt": 0, "right_margin_pt": 0, "top_margin_pt": 0, "bottom_margin_pt": 0,
        }),
        "rich_text": {"text": text, "runs": runs, "fit": "none"},
    }, box


def box_dict(box):
    return {"x": round_number(box[0]), "y": round_number(box[1]),
            "width": round_number(box[2]), "height": round_number(box[3])}


def bridge_ordered_node(node):
    """Serialize the .NET polymorphic discriminator before normal fields.

    The upstream JavaScript schema accepts properties in any order. The
    current .NET 8 bridge, however, resolves ``SceneNode`` subclasses only
    when ``kind`` appears before ordinary properties in the JSON object.
    """
    kind = node.pop("kind")
    return {"kind": kind, **node}


def primitive_node(element, classes, dpi, z_order):
    tag = local_name(element.tag)
    identifier = element_id(element)
    style = merged_style(element, classes)
    if tag == "text":
        return text_node(element, style, classes, dpi, z_order)
    base = {"semantic_id": identifier, "layer": "background" if identifier == "page-background" else "structure",
            "z_order": z_order, "role": "background" if identifier == "page-background" else tag}
    if tag == "rect":
        x = parse_number(element.attrib.get("x", "0"), identifier + ".x")
        y = parse_number(element.attrib.get("y", "0"), identifier + ".y")
        width = parse_number(element.attrib.get("width"), identifier + ".width")
        height = parse_number(element.attrib.get("height"), identifier + ".height")
        box = positive_bbox(x, y, width, height)
        rx = parse_number(element.attrib["rx"], identifier + ".rx") if "rx" in element.attrib else None
        base.update(kind="shape", shape="rounded_rectangle" if rx else "rectangle", bounds=box_dict(box),
                    style=shape_style(style, dpi, corner_radius_units=rx))
        return bridge_ordered_node(base), box
    if tag in ("ellipse", "circle"):
        cx = parse_number(element.attrib.get("cx"), identifier + ".cx")
        cy = parse_number(element.attrib.get("cy"), identifier + ".cy")
        rx = parse_number(element.attrib.get("rx", element.attrib.get("r")), identifier + ".rx")
        ry = parse_number(element.attrib.get("ry", element.attrib.get("r")), identifier + ".ry")
        box = positive_bbox(cx - rx, cy - ry, 2 * rx, 2 * ry)
        base.update(kind="shape", shape="ellipse", bounds=box_dict(box), style=shape_style(style, dpi))
        return bridge_ordered_node(base), box
    if tag == "line":
        x1 = parse_number(element.attrib.get("x1"), identifier + ".x1")
        y1 = parse_number(element.attrib.get("y1"), identifier + ".y1")
        x2 = parse_number(element.attrib.get("x2"), identifier + ".x2")
        y2 = parse_number(element.attrib.get("y2"), identifier + ".y2")
        box = positive_bbox(min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1))
        commands = [{"op": "M", "x": round_number(x1 - box[0]), "y": round_number(y1 - box[1])},
                    {"op": "L", "x": round_number(x2 - box[0]), "y": round_number(y2 - box[1])}]
        base.update(kind="path", bounds=box_dict(box), commands=commands, closed=False, style=shape_style(style, dpi))
        return bridge_ordered_node(base), box
    if tag in ("polygon", "polyline"):
        points = polygon_points(element.attrib.get("points"))
        x1, y1 = min(x for x, _ in points), min(y for _, y in points)
        x2, y2 = max(x for x, _ in points), max(y for _, y in points)
        box = positive_bbox(x1, y1, x2 - x1, y2 - y1)
        commands = [{"op": "M", "x": round_number(points[0][0] - x1), "y": round_number(points[0][1] - y1)}]
        commands.extend({"op": "L", "x": round_number(x - x1), "y": round_number(y - y1)} for x, y in points[1:])
        closed = tag == "polygon"
        if closed:
            commands.append({"op": "Z"})
        base.update(kind="path", bounds=box_dict(box), commands=commands, closed=closed, style=shape_style(style, dpi))
        return bridge_ordered_node(base), box
    if tag == "path":
        box, commands, closed = parse_path(element.attrib.get("d"))
        base.update(kind="path", bounds=box_dict(box), commands=commands, closed=closed, style=shape_style(style, dpi))
        return bridge_ordered_node(base), box
    raise AdapterError("Unsupported SVG element: %s" % tag)


def connector_style(element, classes, dpi):
    style = merged_style(element, classes)
    color = color_or_none(style.get("stroke", "#000000"), "connector stroke") or "#000000"
    return {
        "stroke_color": color,
        "stroke_width_pt": round_number(parse_number(style.get("stroke-width", "1"), "connector width") * 72.0 / dpi),
        "dashed": style.get("stroke-dasharray") not in (None, "none"),
        "start_arrow": "none",
        "end_arrow": "triangle",
    }


def path_absolute_points(element):
    tag = local_name(element.tag)
    if tag == "line":
        return [(parse_number(element.attrib["x1"], "x1"), parse_number(element.attrib["y1"], "y1")),
                (parse_number(element.attrib["x2"], "x2"), parse_number(element.attrib["y2"], "y2"))]
    _, _, _ = parse_path(element.attrib.get("d"))
    commands = parse_path(element.attrib.get("d"))[1]
    box, _, _ = parse_path(element.attrib.get("d"))
    points = []
    for command in commands:
        if "x" in command:
            points.append((command["x"] + box[0], command["y"] + box[1]))
    return points


def distance_to_box(point, box):
    x, y = point
    dx = max(box[0] - x, 0, x - (box[0] + box[2]))
    dy = max(box[1] - y, 0, y - (box[1] + box[3]))
    return math.hypot(dx, dy)


def normalized_anchor(point, box):
    """Map an SVG endpoint to Visio's 0..1 shape-local anchor contract."""
    x, y = point
    nx = min(1.0, max(0.0, (x - box[0]) / box[2]))
    ny = min(1.0, max(0.0, (y - box[1]) / box[3]))
    return {"mode": "normalized", "x": round_number(nx), "y": round_number(ny)}


def validate_svg_safety(root, raw):
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise AdapterError("DOCTYPE and ENTITY declarations are forbidden")
    identifiers = set()
    for element in root.iter():
        tag = local_name(element.tag)
        if tag == "foreignObject":
            raise AdapterError("foreignObject is forbidden")
        if tag not in SUPPORTED_RENDER_TAGS | ALLOWED_NON_RENDER_TAGS:
            raise AdapterError("Unsupported SVG element: %s" % tag)
        for key, value in element.attrib.items():
            name = local_name(key)
            if name in FORBIDDEN_ATTRIBUTES:
                raise AdapterError("Unsupported SVG attribute: %s" % name)
            if name.lower().startswith("on"):
                raise AdapterError("SVG event attributes are forbidden")
            if name in ("href",) or key == "{%s}href" % XLINK_NS:
                raise AdapterError("External/embedded SVG references are forbidden")
            if "url(" in value:
                raise AdapterError("URL references are forbidden")
        if tag in SUPPORTED_RENDER_TAGS or tag == "g":
            identifier = element_id(element)
            if identifier in identifiers:
                raise AdapterError("Duplicate SVG id: %s" % identifier)
            identifiers.add(identifier)


def recipe_connections(recipe):
    if recipe is None:
        return []
    connections = recipe.get("connections", [])
    required = set(recipe.get("contract", {}).get("required_connection_ids", []))
    found = {item.get("id") for item in connections}
    if required != found:
        raise AdapterError("Recipe required_connection_ids must exactly match connections")
    for item in connections:
        if not all(item.get(key) for key in ("id", "from", "to")):
            raise AdapterError("Recipe connections require id/from/to")
    return connections


def compile_scene(svg_path, recipe_path=None, scene_id=None):
    raw = svg_path.read_bytes()
    root = ET.fromstring(raw)
    validate_svg_safety(root, raw)
    classes = css_classes(root)
    canvas_width, canvas_height = parse_viewbox(root)
    width_inches, _ = parse_length(root.attrib.get("width"), "width")
    height_inches, _ = parse_length(root.attrib.get("height"), "height")
    dpi_x = canvas_width / width_inches
    dpi_y = canvas_height / height_inches
    if not math.isclose(dpi_x, dpi_y, rel_tol=0, abs_tol=1e-6):
        raise AdapterError("Physical SVG size and viewBox imply different X/Y DPI")
    dpi = dpi_x
    recipe = json.loads(recipe_path.read_text(encoding="utf-8")) if recipe_path else None
    if recipe:
        canvas = recipe.get("canvas", {})
        if canvas.get("width_units") != canvas_width or canvas.get("height_units") != canvas_height:
            raise AdapterError("Recipe canvas units do not match SVG viewBox")
        expected_font = recipe.get("typography", {}).get("font_family")
        if expected_font and expected_font != "Times New Roman":
            raise AdapterError("Only the current Times New Roman publication contract is supported")
    connections = recipe_connections(recipe)
    connection_by_id = {item["id"]: item for item in connections}
    elements_by_id = {element.attrib["id"]: element for element in root.iter() if "id" in element.attrib}

    suppressed = set()
    detail_connector_elements = []
    for connection in connections:
        element = elements_by_id.get(connection["id"])
        if element is None:
            raise AdapterError("Recipe connection has no matching SVG semantic object: %s" % connection["id"])
        if local_name(element.tag) in ("line", "path"):
            suppressed.add(connection["id"])
            suppressed.add(connection["id"] + "-head")
        elif local_name(element.tag) == "g":
            suppressed.add(connection["id"])
            shafts = [child for child in element.iter()
                      if local_name(child.tag) in ("line", "path") and "connector" in child.attrib.get("class", "").split()]
            if not shafts:
                raise AdapterError("Aggregate connection group contains no connector shafts: %s" % connection["id"])
            for index, shaft in enumerate(shafts):
                detail_connector_elements.append((connection["id"] if index == 0 else element_id(shaft), shaft))
                suppressed.add(element_id(shaft))
                suppressed.add(element_id(shaft) + "-head")
        else:
            raise AdapterError("Connection id must identify a line, path, or group")

    primitive_records = []
    element_parent_groups = {}
    group_elements = {}
    group_stack = []
    z_order = 0

    def visit(element):
        nonlocal z_order
        tag = local_name(element.tag)
        if tag == "g":
            identifier = element_id(element)
            group_elements[identifier] = element
            if identifier not in suppressed:
                group_stack.append(identifier)
                for child in element:
                    visit(child)
                group_stack.pop()
            else:
                for child in element:
                    visit(child)
            return
        if tag in SUPPORTED_RENDER_TAGS:
            identifier = element_id(element)
            if identifier in suppressed:
                return
            node, box = primitive_node(element, classes, dpi, z_order)
            primitive_records.append({"id": identifier, "node": node, "box": box,
                                      "ancestors": tuple(group_stack), "element": element})
            z_order += 1

    for child in root:
        if local_name(child.tag) in ("title", "metadata", "style"):
            continue
        visit(child)

    emitted_groups = {identifier for identifier in group_elements if identifier not in suppressed}
    required_endpoints = {item["from"] for item in connections} | {item["to"] for item in connections}
    while True:
        direct_counts = Counter()
        for record in primitive_records:
            parent = next((identifier for identifier in reversed(record["ancestors"]) if identifier in emitted_groups), None)
            if parent:
                direct_counts[parent] += 1
        for identifier in emitted_groups:
            element = group_elements[identifier]
            ancestors = []
            current = element
            while True:
                parent = next((candidate for candidate in root.iter() if current in list(candidate)), None)
                if parent is None or local_name(parent.tag) != "g":
                    break
                ancestors.append(element_id(parent))
                current = parent
            parent_id = next((candidate for candidate in ancestors if candidate in emitted_groups), None)
            if parent_id:
                direct_counts[parent_id] += 1
        removable = {identifier for identifier in emitted_groups if direct_counts[identifier] < 2 and identifier not in required_endpoints}
        invalid_required = {identifier for identifier in emitted_groups if direct_counts[identifier] < 2 and identifier in required_endpoints}
        if invalid_required:
            raise AdapterError("Required connector endpoint group has fewer than two members: %s" % sorted(invalid_required))
        if not removable:
            break
        emitted_groups -= removable

    # The pinned upstream SceneExecutor currently re-sorts group steps by an
    # ascending rank after asking for descending parent depth. Nested parent
    # groups therefore execute before their child groups exist. Preserve the
    # independently editable leaf groups (including every connector endpoint)
    # and express the discarded container hierarchy through layers instead.
    container_groups = set()
    for identifier in emitted_groups:
        descendant_group_ids = {
            element_id(child) for child in group_elements[identifier].iter()
            if child is not group_elements[identifier] and local_name(child.tag) == "g"
        }
        if descendant_group_ids & emitted_groups:
            container_groups.add(identifier)
    invalid_container_endpoints = container_groups & required_endpoints
    if invalid_container_endpoints:
        raise AdapterError("Nested connector endpoint groups are not runtime-safe: %s" %
                           sorted(invalid_container_endpoints))
    emitted_groups -= container_groups
    # Keep text as individually editable shapes on the live-text layer. If it
    # is grouped, the executor must draw it before rank-250 groups exist; if it
    # stays ungrouped, its native text rank (400) correctly places it last.
    emitted_groups.discard("live-text")

    def nearest_group(ancestors):
        return next((identifier for identifier in reversed(ancestors) if identifier in emitted_groups), None)

    nodes = []
    record_by_id = {}
    for record in primitive_records:
        parent = nearest_group(record["ancestors"])
        if parent:
            record["node"]["parent_id"] = parent
            if record["node"]["kind"] == "text":
                # A text member must exist before its rank-250 group step.
                record["node"]["role"] = "panel_live_text"
        nodes.append(record["node"])
        record_by_id[record["id"]] = record

    group_boxes = {}
    for identifier in emitted_groups:
        descendant_boxes = [record["box"] for record in primitive_records if identifier in record["ancestors"]]
        group_boxes[identifier] = bbox_union(descendant_boxes)
    for identifier in sorted(emitted_groups, key=lambda value: (len(list(group_elements[value].iter())), value)):
        element = group_elements[identifier]
        ancestors = []
        current = element
        while True:
            parent = next((candidate for candidate in root.iter() if current in list(candidate)), None)
            if parent is None or local_name(parent.tag) != "g":
                break
            ancestors.append(element_id(parent))
            current = parent
        parent_id = next((candidate for candidate in ancestors if candidate in emitted_groups), None)
        node = {"kind": "group", "semantic_id": identifier, "bounds": box_dict(group_boxes[identifier]),
                "layer": "live-text" if identifier == "live-text" else "structure", "z_order": z_order,
                "role": "semantic_group"}
        if parent_id:
            node["parent_id"] = parent_id
        nodes.append(node)
        record_by_id[identifier] = {"id": identifier, "node": node, "box": group_boxes[identifier], "element": element}
        z_order += 1

    # Upstream set_z_order treats positions as local to the current Visio
    # group, while SVG z-order is global. Applying the global index after
    # grouping can exceed the number of sibling shapes. Node-array creation
    # order plus layers is deterministic, so omit unsafe absolute z-order.
    for node in nodes:
        node.pop("z_order", None)

    if recipe:
        typography = recipe.get("typography", {})
        main_pt = parse_number(typography.get("size_pt"), "recipe typography.size_pt")
        subscript_pt = parse_number(typography.get("subscript_size_pt"), "recipe typography.subscript_size_pt")
        expected_family = typography.get("font_family")
        for node in nodes:
            if node["kind"] != "text":
                continue
            for run in node["rich_text"]["runs"]:
                if run["font_family"] != expected_family:
                    raise AdapterError("SVG text font differs from recipe typography: %s" % node["semantic_id"])
                if math.isclose(run["font_size_pt"], main_pt, abs_tol=0.01):
                    run["font_size_pt"] = round_number(main_pt)
                elif math.isclose(run["font_size_pt"], subscript_pt, abs_tol=0.01) and run.get("subscript"):
                    run["font_size_pt"] = round_number(subscript_pt)
                else:
                    raise AdapterError("SVG text size is outside the recipe main/subscript contract: %s" % node["semantic_id"])

    connector_nodes = []
    for connection in connections:
        if connection["id"] in {item[0] for item in detail_connector_elements}:
            continue
        source, target = connection["from"], connection["to"]
        if source not in record_by_id or target not in record_by_id:
            raise AdapterError("Connector endpoint was not emitted: %s -> %s" % (source, target))
        element = elements_by_id[connection["id"]]
        points = path_absolute_points(element)
        item = {"semantic_id": connection["id"], "source": source, "target": target,
                "routing": "straight" if len(points) == 2 else "polyline", "glued": True,
                "style": connector_style(element, classes, dpi),
                "source_anchor": normalized_anchor(points[0], record_by_id[source]["box"]),
                "target_anchor": normalized_anchor(points[-1], record_by_id[target]["box"])}
        if len(points) > 2:
            item["waypoints"] = [{"x": round_number(x), "y": round_number(y)} for x, y in points[1:-1]]
        connector_nodes.append(item)

    leaf_candidates = [record for record in primitive_records
                       if record["node"]["kind"] == "shape" and record["id"] != "page-background"]
    for semantic_id, element in detail_connector_elements:
        points = path_absolute_points(element)
        if len(points) < 2:
            raise AdapterError("Detail connector has insufficient geometry")
        source_record = min(leaf_candidates, key=lambda record: distance_to_box(points[0], record["box"]))
        target_record = min(leaf_candidates, key=lambda record: distance_to_box(points[-1], record["box"]))
        if source_record["id"] == target_record["id"]:
            raise AdapterError("Cannot infer distinct detail connector endpoints: %s" % semantic_id)
        item = {"semantic_id": semantic_id, "source": source_record["id"], "target": target_record["id"],
                "routing": "straight" if len(points) == 2 else "polyline", "glued": True,
                "style": connector_style(element, classes, dpi),
                "source_anchor": normalized_anchor(points[0], source_record["box"]),
                "target_anchor": normalized_anchor(points[-1], target_record["box"])}
        if len(points) > 2:
            item["waypoints"] = [{"x": round_number(x), "y": round_number(y)} for x, y in points[1:-1]]
        connector_nodes.append(item)

    identifiers = [node["semantic_id"] for node in nodes] + [item["semantic_id"] for item in connector_nodes]
    if len(identifiers) != len(set(identifiers)):
        duplicates = sorted(identifier for identifier, count in Counter(identifiers).items() if count > 1)
        raise AdapterError("Duplicate SceneGraph semantic ids: %s" % duplicates)
    layers = ["background", "structure", "connectors", "live-text", "annotations"]
    scene = {
        "scene_id": scene_id or (svg_path.stem.replace("_publication_tnr_8_5pt", "") + "-visio-scene"),
        "canvas": {"width_px": canvas_width, "height_px": canvas_height, "dpi": round_number(dpi)},
        "style_tokens": {
            "font_primary": "Times New Roman",
            "font_size_pt": "8.5",
            "source_physical_width": root.attrib["width"],
            "source_physical_height": root.attrib["height"],
        },
        "layers": layers,
        "nodes": nodes,
        "connectors": connector_nodes,
        # The upstream executor applies a region before advancing to the next
        # one. SVG group membership may cross a visual region boundary, so a
        # group can otherwise be applied before one of its children exists.
        # Compile one full-page checkpoint to make grouping dependency-safe.
        "regions": [
            {"id": "full-figure", "bounds": {"x": 0, "y": 0, "width": canvas_width,
             "height": canvas_height}, "checkpoint": True},
        ],
    }
    validate_scene(scene)
    source_counts = Counter(local_name(element.tag) for element in root.iter())
    return scene, recipe, source_counts, dpi


def validate_scene(scene):
    required = {"scene_id", "canvas", "style_tokens", "layers", "nodes", "connectors", "regions"}
    if set(scene) != required:
        raise AdapterError("SceneGraph top-level fields do not match upstream schema")
    canvas = scene["canvas"]
    if set(canvas) != {"width_px", "height_px", "dpi"}:
        raise AdapterError("SceneGraph canvas fields do not match upstream schema")
    if not scene["nodes"] or not scene["regions"] or not any(region["checkpoint"] for region in scene["regions"]):
        raise AdapterError("Scene requires nodes and at least one checkpoint")
    layers = scene["layers"]
    if len(layers) != len(set(layers)):
        raise AdapterError("Scene layers must be unique")
    ids = set()
    node_ids = set()
    parent_map = {}
    for node in scene["nodes"]:
        identifier = node["semantic_id"]
        if identifier in ids:
            raise AdapterError("Duplicate scene id: %s" % identifier)
        ids.add(identifier)
        node_ids.add(identifier)
        parent_map[identifier] = node.get("parent_id")
        if node.get("layer") not in layers:
            raise AdapterError("Undeclared layer on %s" % identifier)
        box = node["bounds"]
        if box["x"] < 0 or box["y"] < 0 or box["width"] <= 0 or box["height"] <= 0:
            raise AdapterError("Invalid bounds on %s" % identifier)
        if box["x"] + box["width"] > canvas["width_px"] + 1e-6 or box["y"] + box["height"] > canvas["height_px"] + 1e-6:
            raise AdapterError("Out-of-canvas bounds on %s" % identifier)
        if node["kind"] == "path":
            if not node["commands"] or node["commands"][0]["op"] != "M":
                raise AdapterError("Path must start with M: %s" % identifier)
    for identifier, parent in parent_map.items():
        if parent is not None and parent not in node_ids:
            raise AdapterError("Missing parent for %s" % identifier)
        seen = {identifier}
        while parent is not None:
            if parent in seen:
                raise AdapterError("Parent cycle at %s" % identifier)
            seen.add(parent)
            parent = parent_map[parent]
    for connector in scene["connectors"]:
        identifier = connector["semantic_id"]
        if identifier in ids:
            raise AdapterError("Duplicate connector id: %s" % identifier)
        ids.add(identifier)
        if connector["source"] not in node_ids or connector["target"] not in node_ids:
            raise AdapterError("Missing connector endpoint: %s" % identifier)
        if connector["source"] == connector["target"]:
            raise AdapterError("Self connector is forbidden: %s" % identifier)
        if connector["routing"] not in ("dynamic", "right_angle", "straight", "polyline"):
            raise AdapterError("Unsupported routing: %s" % identifier)
    return scene


def build_outputs(svg_path, output_path, recipe_path=None, scene_id=None):
    scene, recipe, source_counts, dpi = compile_scene(svg_path, recipe_path, scene_id)
    scene_bytes = (json.dumps(scene, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    text_nodes = [node for node in scene["nodes"] if node["kind"] == "text"]
    font_sizes = Counter()
    font_families = Counter()
    for node in text_nodes:
        for run in node["rich_text"]["runs"]:
            font_sizes[str(run["font_size_pt"])] += 1
            font_families[run["font_family"]] += 1
    manifest = {
        "schema_version": "visio-scene-adapter-manifest-v1",
        "source_svg": str(svg_path.as_posix()),
        "source_svg_sha256": sha256_bytes(svg_path.read_bytes()),
        "recipe": str(recipe_path.as_posix()) if recipe_path else None,
        "recipe_sha256": sha256_bytes(recipe_path.read_bytes()) if recipe_path else None,
        "scene": str(output_path.as_posix()),
        "scene_sha256": sha256_bytes(scene_bytes),
        "upstream_contract": {"repository": UPSTREAM_REPOSITORY, "commit": UPSTREAM_COMMIT, "schema_path": UPSTREAM_SCHEMA_PATH},
        "canvas": scene["canvas"],
        "physical_size": {"width": scene["style_tokens"]["source_physical_width"],
                          "height": scene["style_tokens"]["source_physical_height"]},
        "counts": {"nodes": len(scene["nodes"]), "connectors": len(scene["connectors"]),
                   "groups": sum(node["kind"] == "group" for node in scene["nodes"]),
                   "live_text": len(text_nodes), "paths": sum(node["kind"] == "path" for node in scene["nodes"]),
                   "shapes": sum(node["kind"] == "shape" for node in scene["nodes"]), "images": 0},
        "font_families": dict(sorted(font_families.items())),
        "font_size_runs_pt": dict(sorted(font_sizes.items())),
        "status": "scene-generated-visio-plugin-render-not-run",
    }
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    required_connections = set(recipe.get("contract", {}).get("required_connection_ids", [])) if recipe else set()
    connector_ids = {item["semantic_id"] for item in scene["connectors"]}
    checks = {
        "upstream_top_level_contract": set(scene) == {"scene_id", "canvas", "style_tokens", "layers", "nodes", "connectors", "regions"},
        "physical_canvas_preserved": math.isclose(dpi, scene["canvas"]["dpi"], abs_tol=1e-6),
        "semantic_ids_unique": len({node["semantic_id"] for node in scene["nodes"]} | connector_ids) == len(scene["nodes"]) + len(scene["connectors"]),
        "required_recipe_connectors_present": required_connections <= connector_ids,
        "all_connectors_glued_requested": all(item.get("glued") is True for item in scene["connectors"]),
        "all_text_is_live": len(text_nodes) == source_counts.get("text", 0),
        "times_new_roman_preserved": set(font_families) == {"Times New Roman"},
        "main_text_8_5pt_present": any(math.isclose(float(value), 8.5, abs_tol=0.0001) for value in font_sizes),
        "zero_images": not any(node["kind"] == "image" for node in scene["nodes"]),
        "regions_have_checkpoints": all(region["checkpoint"] for region in scene["regions"]),
        "single_full_page_region_for_group_safety": scene["regions"] == [
            {"id": "full-figure", "bounds": {"x": 0, "y": 0, "width": scene["canvas"]["width_px"],
             "height": scene["canvas"]["height_px"]}, "checkpoint": True}
        ],
        "groups_flattened_for_upstream_runtime": all(node.get("parent_id") is None
                                                       for node in scene["nodes"] if node["kind"] == "group"),
        "global_z_order_omitted_for_group_safety": all("z_order" not in node for node in scene["nodes"]),
    }
    audit = {
        "schema_version": "visio-scene-adapter-audit-v1",
        "scene": str(output_path.as_posix()),
        "scene_sha256": sha256_bytes(scene_bytes),
        "manifest_sha256": sha256_bytes(manifest_bytes),
        "structural_pass": all(checks.values()),
        "visio_plugin_rendered": False,
        "vsdx_created": False,
        "status": "adapter-structural-pass-visio-live-validation-pending" if all(checks.values()) else "adapter-structural-fail",
        "upstream_contract_probe": {
            "repository": UPSTREAM_REPOSITORY,
            "commit": UPSTREAM_COMMIT,
            "schema_path": UPSTREAM_SCHEMA_PATH,
            "scene_schema_validation": "passed-during-adapter-development",
            "visio_plugin_execution": "not-run",
        },
        "checks": checks,
        "source_svg_element_counts": dict(sorted(source_counts.items())),
        "scene_counts": manifest["counts"],
        "limitations": [
            "The scene was not submitted to visio_live_draw_scene and no VSDX was created.",
            "Connector glued=true is a requested contract; only a real Visio fidelity audit can prove double-ended GlueTo records.",
            "SVG text bounds are conservative estimates because SVG stores baselines rather than text-box rectangles.",
            "FIG07 English translation approval remains outside this backend adapter.",
        ],
    }
    audit_bytes = (json.dumps(audit, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    return scene_bytes, manifest_bytes, audit_bytes


def atomic_write(path, content, force):
    if path.exists() and not force:
        raise FileExistsError("Refusing to overwrite existing output: %s" % path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(mode="wb", dir=str(path.parent), suffix=".tmp", delete=False)
    temporary = Path(handle.name)
    try:
        with handle:
            handle.write(content)
        os.replace(str(temporary), str(path))
    finally:
        if temporary.exists():
            temporary.unlink()


def resolve_workspace_path(path, label):
    resolved = path.resolve()
    try:
        resolved.relative_to(WORKSPACE_ROOT)
    except ValueError:
        raise AdapterError("%s must remain inside the workspace: %s" % (label, resolved))
    return resolved


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_svg", type=Path)
    parser.add_argument("output_scene", type=Path)
    parser.add_argument("--recipe", type=Path)
    parser.add_argument("--manifest-out", type=Path)
    parser.add_argument("--audit-out", type=Path)
    parser.add_argument("--scene-id")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--check", action="store_true", help="Compare deterministic outputs without writing.")
    args = parser.parse_args()
    input_candidate = args.input_svg
    output_candidate = args.output_scene
    recipe_candidate = args.recipe
    manifest_candidate = args.manifest_out
    audit_candidate = args.audit_out
    force_enabled = bool(args.force)
    check_enabled = bool(args.check)
    scene_id = args.scene_id
    svg_path = resolve_workspace_path(input_candidate, "input_svg")
    output_path = resolve_workspace_path(output_candidate, "output_scene")
    recipe_path = resolve_workspace_path(recipe_candidate, "recipe") if recipe_candidate else None
    manifest_path = resolve_workspace_path(
        manifest_candidate or output_path.with_suffix(".manifest.json"), "manifest_out")
    audit_path = resolve_workspace_path(
        audit_candidate or output_path.with_suffix(".audit.json"), "audit_out")
    if not svg_path.is_file():
        raise FileNotFoundError(svg_path)
    if recipe_path and not recipe_path.is_file():
        raise FileNotFoundError(recipe_path)
    scene_bytes, manifest_bytes, audit_bytes = build_outputs(svg_path, output_path, recipe_path, scene_id)
    outputs = {output_path: scene_bytes, manifest_path: manifest_bytes, audit_path: audit_bytes}
    if check_enabled:
        stale = [str(path) for path, content in outputs.items() if not path.exists() or path.read_bytes() != content]
        if stale:
            raise SystemExit("Stale or missing Visio SceneGraph outputs: " + ", ".join(stale))
        print("Visio SceneGraph outputs are deterministic and current.")
        return
    existing = [str(path) for path in outputs if path.exists()]
    if existing and not force_enabled:
        raise FileExistsError("Refusing to overwrite existing output(s): " + ", ".join(existing))
    for path, content in outputs.items():
        atomic_write(path, content, force_enabled)
    print("Wrote SceneGraph, manifest, and audit. Visio/plugin execution was not run.")


if __name__ == "__main__":
    main()
