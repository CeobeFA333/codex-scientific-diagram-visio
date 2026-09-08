from __future__ import annotations

import argparse
import base64
import hashlib
import html
import io
import json
import math
import os
import re
import statistics
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Tuple

from PIL import Image, ImageColor, ImageDraw


PT_PER_MM = 72.0 / 25.4
CSS_PX_PER_MM = 96.0 / 25.4
CSS_PX_PER_PT = 96.0 / 72.0
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "references" / "reconstruction-spec.schema.json"
PixelRect = Tuple[int, int, int, int]


@dataclass(frozen=True)
class ColorRemovalConfig:
    red_min: int
    dominance_min: int
    radius: int


@dataclass(frozen=True)
class RasterRenderContext:
    px: Callable[[float], str]
    width_user: float
    height_user: float


def workspace_path(raw: str, *, must_exist: bool = False) -> Path:
    workspace = Path.cwd().resolve()
    path = Path(raw)
    path = (path if path.is_absolute() else workspace / path).resolve()
    if path != workspace and workspace not in path.parents:
        raise ValueError(f"Path must stay inside workspace: {path}")
    if must_exist and not path.exists():
        raise FileNotFoundError(path)
    return path


def require_new_output(path: Path, overwrite: bool = False) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"Output already exists; choose a new name or pass --force: {path}")


def atomic_write_text(path: Path, content: str, overwrite: bool = False) -> None:
    require_new_output(path, overwrite)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        suffix=path.suffix,
        prefix=f".{path.stem}-",
        dir=path.parent,
        delete=False,
    )
    temporary = Path(handle.name)
    try:
        with handle:
            handle.write(content)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def image_rect(box: list[float], size: tuple[int, int]) -> PixelRect:
    x, y, width, height = box
    left = max(0, round(x))
    top = max(0, round(y))
    right = min(size[0], round(x + width))
    bottom = min(size[1], round(y + height))
    if right <= left or bottom <= top:
        raise ValueError(f"Invalid mask rectangle: {box}")
    return left, top, right, bottom


def strict_image_rect(box: list[float], size: tuple[int, int], *, label: str) -> PixelRect:
    if len(box) != 4:
        raise ValueError(f"{label} must contain x, y, width, height")
    x, y, width, height = (float(value) for value in box)
    if any(not value.is_integer() for value in (x, y, width, height)):
        raise ValueError(f"{label} must use integer pixel coordinates")
    if x < 0 or y < 0 or width <= 0 or height <= 0:
        raise ValueError(f"{label} must be a positive rectangle inside its image")
    if x + width > size[0] + 1e-6 or y + height > size[1] + 1e-6:
        raise ValueError(f"{label} exceeds image bounds {size}")
    return round(x), round(y), round(x + width), round(y + height)


def rectangle_area(box: list[float]) -> float:
    return float(box[2]) * float(box[3])


def rectangle_union_area(boxes: list[list[float]]) -> float:
    if not boxes:
        return 0.0
    x_values = sorted({float(box[0]) for box in boxes} | {float(box[0]) + float(box[2]) for box in boxes})
    total = 0.0
    for left, right in zip(x_values, x_values[1:]):
        intervals = sorted(
            (float(box[1]), float(box[1]) + float(box[3]))
            for box in boxes
            if float(box[0]) < right and float(box[0]) + float(box[2]) > left
        )
        covered_y = 0.0
        if intervals:
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


def is_remove_color(color: tuple[int, int, int], red_min: int, dominance_min: int) -> bool:
    return color[0] >= red_min and color[0] - max(color[1], color[2]) >= dominance_min


def rectangles_intersect(first: list[float], second: list[float]) -> bool:
    ax, ay, aw, ah = first
    bx, by, bw, bh = second
    return ax < bx + bw and ax + aw > bx and ay < by + bh and ay + ah > by


def rectangle_contains(outer: list[float], inner: list[float]) -> bool:
    ox, oy, ow, oh = (float(value) for value in outer)
    ix, iy, iw, ih = (float(value) for value in inner)
    return ix >= ox and iy >= oy and ix + iw <= ox + ow and iy + ih <= oy + oh


def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_canvas(recipe: dict, source_size: tuple[int, int] | None) -> tuple[int, int]:
    canvas = recipe["canvas"]
    for key in ("width_px", "height_px", "print_width_mm"):
        if float(canvas.get(key, 0)) <= 0:
            raise ValueError(f"canvas.{key} must be positive")
    canvas_size = (int(canvas["width_px"]), int(canvas["height_px"]))
    if source_size is not None and canvas_size != source_size:
        raise ValueError(f"Recipe canvas {canvas_size} does not match source {source_size}")
    return canvas_size


def validate_mask(mask: dict, canvas_size: tuple[int, int], modes: set[str], protected: list[dict]) -> None:
    if "rect_px" not in mask or "mode" not in mask:
        raise ValueError("Each mask requires rect_px and mode")
    image_rect(mask["rect_px"], canvas_size)
    mode = mask["mode"]
    if mode not in modes:
        raise ValueError(f"Unsupported mask mode: {mode}")
    required_field = {"sample": "sample_px", "clone": "source_rect_px"}.get(mode)
    if required_field and required_field not in mask:
        raise ValueError(f"{mode} mask requires {required_field}")
    intersections = [region["id"] for region in protected if rectangles_intersect(mask["rect_px"], region["rect_px"])]
    if intersections:
        raise ValueError(
            f"Mask {mask['rect_px']} intersects protected scientific pixels: {', '.join(intersections)}"
        )


def validate_masks(recipe: dict, canvas_size: tuple[int, int], schema: dict) -> None:
    protected = recipe.get("protected_regions_px", [])
    for region in protected:
        if not region.get("id") or "rect_px" not in region:
            raise ValueError("Each protected region requires id and rect_px")
        image_rect(region["rect_px"], canvas_size)
    modes = set(schema["properties"]["masks"]["items"]["properties"]["mode"]["enum"])
    for mask in recipe.get("masks", []):
        validate_mask(mask, canvas_size, modes, protected)


def validate_path_commands(element_id: str, commands: list[dict]) -> None:
    required_by_operation = {
        "M": ("x_px", "y_px"),
        "L": ("x_px", "y_px"),
        "C": ("x1_px", "y1_px", "x2_px", "y2_px", "x_px", "y_px"),
        "Q": ("x1_px", "y1_px", "x_px", "y_px"),
        "A": (
            "rx_px",
            "ry_px",
            "x_axis_rotation_deg",
            "large_arc",
            "sweep",
            "x_px",
            "y_px",
        ),
        "Z": (),
    }
    if not commands:
        raise ValueError(f"Path {element_id} requires at least one command")
    if commands[0].get("op") != "M":
        raise ValueError(f"Path {element_id} must begin with M")
    for index, command in enumerate(commands):
        operation = command.get("op")
        if operation not in required_by_operation:
            raise ValueError(f"Path {element_id} has unsupported command at {index}: {operation}")
        missing = [field for field in required_by_operation[operation] if field not in command]
        if missing:
            raise ValueError(
                f"Path {element_id} command {index} is missing: {', '.join(missing)}"
            )
        if operation == "A" and (float(command["rx_px"]) <= 0 or float(command["ry_px"]) <= 0):
            raise ValueError(f"Path {element_id} arc radii must be positive")


def validate_element(
    element: dict,
    element_types: set[str],
    existing_ids: set[str],
    gradient_ids: set[str],
) -> None:
    required_by_type = {
        "text": ("x_px", "y_px"),
        "line": ("x1_px", "y1_px", "x2_px", "y2_px"),
        "rect": ("x_px", "y_px", "width_px", "height_px"),
        "ellipse": ("cx_px", "cy_px", "rx_px", "ry_px"),
        "polyline": ("points_px",),
        "polygon": ("points_px",),
        "path": ("commands",),
        "arc": ("cx_px", "cy_px", "radius_px", "start_angle_deg", "end_angle_deg"),
        "annular_sector": (
            "cx_px",
            "cy_px",
            "inner_radius_px",
            "outer_radius_px",
            "start_angle_deg",
            "end_angle_deg",
        ),
        "group": ("children",),
        "text_path": (
            "cx_px",
            "cy_px",
            "radius_px",
            "start_angle_deg",
            "end_angle_deg",
        ),
    }
    kind = element.get("type")
    element_id = element.get("id")
    if kind not in element_types or not element_id:
        raise ValueError("Each element requires a supported type and non-empty id")
    if element_id in existing_ids:
        raise ValueError(f"Duplicate element id: {element_id}")
    missing_fields = [field for field in required_by_type[kind] if field not in element]
    if kind in {"text", "text_path"} and not ("text" in element or element.get("runs")):
        missing_fields.append("text or runs")
    if missing_fields:
        raise ValueError(f"Element {element_id} is missing: {', '.join(missing_fields)}")
    if element.get("fill_gradient") and element["fill_gradient"] not in gradient_ids:
        raise ValueError(
            f"Element {element_id} references unknown gradient: {element['fill_gradient']}"
        )
    if kind in {"polygon", "polyline"}:
        minimum = 3 if kind == "polygon" else 2
        if len(element["points_px"]) < minimum:
            raise ValueError(f"Element {element_id} requires at least {minimum} points")
    if kind == "path":
        validate_path_commands(element_id, element["commands"])
    if kind in {"arc", "text_path"} and float(element["radius_px"]) <= 0:
        raise ValueError(f"Element {element_id} radius must be positive")
    if kind == "annular_sector":
        inner = float(element["inner_radius_px"])
        outer = float(element["outer_radius_px"])
        if inner <= 0 or outer <= inner:
            raise ValueError(
                f"Element {element_id} requires 0 < inner_radius_px < outer_radius_px"
            )
    existing_ids.add(element_id)
    if kind == "text_path":
        curve_id = f"{element_id}__curve"
        if curve_id in existing_ids:
            raise ValueError(
                f"Generated text-path id collides with an element id: {curve_id}"
            )
        existing_ids.add(curve_id)
    if kind == "group":
        if not isinstance(element["children"], list) or not element["children"]:
            raise ValueError(f"Group {element_id} requires at least one child")
        for child in element["children"]:
            validate_element(child, element_types, existing_ids, gradient_ids)


def validate_gradients(recipe: dict) -> set[str]:
    identifiers = set()
    for gradient in recipe.get("gradients", []):
        gradient_id = gradient.get("id")
        gradient_type = gradient.get("type")
        if not gradient_id or gradient_id in identifiers:
            raise ValueError("Each gradient requires a unique non-empty id")
        if gradient_type not in {"linear", "radial"}:
            raise ValueError(f"Unsupported gradient type: {gradient_type}")
        required = (
            ("x1_px", "y1_px", "x2_px", "y2_px")
            if gradient_type == "linear"
            else ("cx_px", "cy_px", "radius_px")
        )
        missing = [field for field in required if field not in gradient]
        if missing:
            raise ValueError(f"Gradient {gradient_id} is missing: {', '.join(missing)}")
        if gradient_type == "radial" and float(gradient["radius_px"]) <= 0:
            raise ValueError(f"Gradient {gradient_id} radius must be positive")
        stops = gradient.get("stops", [])
        if len(stops) < 2:
            raise ValueError(f"Gradient {gradient_id} requires at least two stops")
        offsets = [float(stop["offset_percent"]) for stop in stops]
        if any(offset < 0 or offset > 100 for offset in offsets) or offsets != sorted(offsets):
            raise ValueError(f"Gradient {gradient_id} offsets must be sorted from 0 to 100")
        identifiers.add(gradient_id)
    return identifiers


def validate_elements(recipe: dict, schema: dict, gradient_ids: set[str]) -> set[str]:
    element_types = set(
        schema["properties"]["elements"]["items"]["properties"]["type"]["enum"]
    )
    ids = set(gradient_ids)
    for element in recipe["elements"]:
        validate_element(element, element_types, ids, gradient_ids)
    return ids


def flatten_elements(elements: list[dict]) -> list[dict]:
    flattened = []
    for element in elements:
        flattened.append(element)
        if element.get("type") == "group":
            flattened.extend(flatten_elements(element.get("children", [])))
    return flattened


def validate_raster_regions(
    recipe: dict, canvas_size: tuple[int, int], reserved_ids: set[str] | None = None
) -> None:
    required = {
        "id",
        "source_rect_px",
        "raster_reason",
        "atomic_raster_unit",
        "contains_reconstructable_content",
        "decomposition_note",
    }
    ids = set(reserved_ids or ())
    atomic_canvas_boxes = []
    for region in recipe.get("raster_regions", []):
        missing = sorted(required - set(region))
        if missing:
            raise ValueError(f"Raster region is missing: {', '.join(missing)}")
        if region["id"] in ids:
            raise ValueError(f"Duplicate raster region id: {region['id']}")
        ids.add(region["id"])
        source_box = region["source_rect_px"]
        destination = region.get("dest_rect_px", source_box)
        image_rect(source_box, canvas_size)
        image_rect(destination, canvas_size)
        if region["atomic_raster_unit"]:
            source_ratio = float(source_box[2]) / float(source_box[3])
            destination_ratio = float(destination[2]) / float(destination[3])
            if not math.isclose(source_ratio, destination_ratio, rel_tol=1e-6, abs_tol=1e-9):
                raise ValueError(f"Atomic raster {region['id']} would require nonuniform scaling")
            if math.isclose(
                rectangle_area(destination), canvas_size[0] * canvas_size[1], rel_tol=1e-9
            ):
                raise ValueError(f"Atomic raster {region['id']} cannot cover the full canvas")
            atomic_canvas_boxes.append(destination)
    if atomic_canvas_boxes and math.isclose(
        rectangle_union_area(atomic_canvas_boxes),
        canvas_size[0] * canvas_size[1],
        rel_tol=1e-9,
        abs_tol=1e-6,
    ):
        raise ValueError("Atomic raster regions cannot collectively cover the full canvas")


def validate_atomic_rasters(
    recipe: dict, canvas_size: tuple[int, int], reserved_ids: set[str] | None = None
) -> None:
    if "atomic_rasters" not in recipe:
        return
    if recipe.get("raster_regions"):
        raise ValueError("Use atomic_rasters or legacy raster_regions, not both")
    regions = recipe["atomic_rasters"]
    if not regions:
        raise ValueError("atomic_rasters requires at least one field")
    required = {
        "id",
        "source_file",
        "cleaned_file",
        "source_bbox_px",
        "canvas_bbox_px",
        "evidence",
        "raster_reason",
        "decomposition_note",
        "allow_nonuniform_scale",
    }
    identifiers = set(reserved_ids or ())
    canvas_boxes = []
    for region in regions:
        missing = sorted(required - set(region))
        if missing:
            raise ValueError(f"Atomic raster field is missing: {', '.join(missing)}")
        identifier = region["id"]
        if not identifier or identifier in identifiers:
            raise ValueError(f"Duplicate or reserved atomic raster id: {identifier}")
        identifiers.add(identifier)
        if not str(region["source_file"]).strip() or not str(region["cleaned_file"]).strip():
            raise ValueError(f"Atomic raster {identifier} requires source_file and cleaned_file")
        if region["evidence"] is not True:
            raise ValueError(f"Atomic raster {identifier} evidence must be true")
        if region["allow_nonuniform_scale"] is not False:
            raise ValueError(f"Atomic raster {identifier} cannot allow nonuniform scaling")
        if not str(region["raster_reason"]).strip() or not str(region["decomposition_note"]).strip():
            raise ValueError(f"Atomic raster {identifier} requires reason and decomposition note")
        source_box = region["source_bbox_px"]
        canvas_box = region["canvas_bbox_px"]
        strict_image_rect(canvas_box, canvas_size, label=f"atomic_rasters[{identifier}].canvas_bbox_px")
        if len(source_box) != 4 or float(source_box[0]) < 0 or float(source_box[1]) < 0:
            raise ValueError(f"atomic_rasters[{identifier}].source_bbox_px is invalid")
        if float(source_box[2]) <= 0 or float(source_box[3]) <= 0:
            raise ValueError(f"atomic_rasters[{identifier}].source_bbox_px must be positive")
        source_ratio = float(source_box[2]) / float(source_box[3])
        canvas_ratio = float(canvas_box[2]) / float(canvas_box[3])
        if not math.isclose(source_ratio, canvas_ratio, rel_tol=1e-6, abs_tol=1e-9):
            raise ValueError(f"Atomic raster {identifier} would require nonuniform scaling")
        if math.isclose(rectangle_area(canvas_box), canvas_size[0] * canvas_size[1], rel_tol=1e-9):
            raise ValueError(f"Atomic raster {identifier} cannot cover the full canvas")
        canvas_boxes.append(canvas_box)
    if math.isclose(
        rectangle_union_area(canvas_boxes),
        canvas_size[0] * canvas_size[1],
        rel_tol=1e-9,
        abs_tol=1e-6,
    ):
        raise ValueError("Atomic raster fields cannot collectively cover the full canvas")


def map_atomic_source_rect_to_canvas(mask_rect: list[float], atomic: dict) -> list[float]:
    source_x, source_y, source_width, source_height = (
        float(value) for value in atomic["source_bbox_px"]
    )
    canvas_x, canvas_y, canvas_width, canvas_height = (
        float(value) for value in atomic["canvas_bbox_px"]
    )
    mask_x, mask_y, mask_width, mask_height = (float(value) for value in mask_rect)
    return [
        canvas_x + (mask_x - source_x) * canvas_width / source_width,
        canvas_y + (mask_y - source_y) * canvas_height / source_height,
        mask_width * canvas_width / source_width,
        mask_height * canvas_height / source_height,
    ]


def validate_annotation_occlusion_masks(
    recipe: dict,
    canvas_size: tuple[int, int],
    reserved_ids: set[str],
) -> None:
    masks = recipe.get("annotation_occlusion_masks", [])
    if not masks:
        return
    atomic_by_id = {region["id"]: region for region in recipe.get("atomic_rasters", [])}
    if not atomic_by_id:
        raise ValueError("annotation_occlusion_masks require atomic_rasters")
    elements = {
        element["id"]: element
        for element in flatten_elements(recipe.get("elements", []))
    }
    identifiers = set(reserved_ids) | set(atomic_by_id) | {"annotation-occlusion-masks"}
    protected = recipe.get("protected_regions_px", [])
    for mask in masks:
        missing = sorted(
            {
                "id",
                "atomic_raster_id",
                "rect_px",
                "mode",
                "fill",
                "max_area_fraction",
                "evidence_change_contract",
                "source_crop_sha256",
                "old_annotation_risk",
                "approval_status",
                "rationale",
                "replacement_element_ids",
            }
            - set(mask)
        )
        if missing:
            raise ValueError(f"Annotation occlusion mask is missing: {', '.join(missing)}")
        identifier = mask["id"]
        if not identifier or identifier in identifiers:
            raise ValueError(f"Duplicate or reserved annotation occlusion mask id: {identifier}")
        identifiers.add(identifier)
        atomic = atomic_by_id.get(mask["atomic_raster_id"])
        if atomic is None:
            raise ValueError(
                f"Annotation occlusion mask {identifier} references an unknown atomic raster"
            )
        rect = [float(value) for value in mask["rect_px"]]
        if len(rect) != 4 or rect[0] < 0 or rect[1] < 0 or rect[2] <= 0 or rect[3] <= 0:
            raise ValueError(f"Annotation occlusion mask {identifier} has an invalid rect_px")
        if not rectangle_contains(atomic["source_bbox_px"], rect):
            raise ValueError(
                f"Annotation occlusion mask {identifier} must stay inside atomic raster source_bbox_px"
            )
        maximum = float(mask["max_area_fraction"])
        if maximum <= 0 or maximum > 0.25:
            raise ValueError(
                f"Annotation occlusion mask {identifier} max_area_fraction must be in (0, 0.25]"
            )
        actual_fraction = rectangle_area(rect) / rectangle_area(atomic["source_bbox_px"])
        if actual_fraction > maximum + 1e-12:
            raise ValueError(
                f"Annotation occlusion mask {identifier} exceeds its declared max_area_fraction"
            )
        if mask["mode"] not in {"plate", "narrow_mask"}:
            raise ValueError(f"Unsupported annotation occlusion mode: {mask['mode']}")
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", str(mask["fill"])):
            raise ValueError(f"Annotation occlusion mask {identifier} requires a solid #RRGGBB fill")
        if mask["evidence_change_contract"] != "source_pixels_immutable":
            raise ValueError(
                f"Annotation occlusion mask {identifier} must keep source pixels immutable"
            )
        if not re.fullmatch(r"[0-9a-f]{64}", str(mask["source_crop_sha256"])):
            raise ValueError(
                f"Annotation occlusion mask {identifier} requires a lowercase source_crop_sha256"
            )
        if mask["old_annotation_risk"] not in {
            "confirmed_occluded",
            "residual_risk",
            "not_reviewed",
        }:
            raise ValueError(f"Annotation occlusion mask {identifier} has an invalid risk status")
        if mask["approval_status"] not in {"approved", "pending", "rejected"}:
            raise ValueError(f"Annotation occlusion mask {identifier} has an invalid approval status")
        if not str(mask["rationale"]).strip():
            raise ValueError(f"Annotation occlusion mask {identifier} requires a rationale")
        if mask["approval_status"] == "approved" and (
            not str(mask.get("approved_by", "")).strip()
            or not str(mask.get("approval_note", "")).strip()
        ):
            raise ValueError(
                f"Approved annotation occlusion mask {identifier} requires approved_by and approval_note"
            )
        if mask["approval_status"] == "rejected":
            raise ValueError(f"Annotation occlusion mask {identifier} has been rejected")
        if (
            mask["approval_status"] == "approved"
            and mask["old_annotation_risk"] != "confirmed_occluded"
        ):
            raise ValueError(
                f"Annotation occlusion mask {identifier} cannot be approved while old annotation risk remains"
            )
        replacement_ids = mask["replacement_element_ids"]
        if (
            not isinstance(replacement_ids, list)
            or not replacement_ids
            or len(replacement_ids) != len(set(replacement_ids))
        ):
            raise ValueError(
                f"Annotation occlusion mask {identifier} requires unique replacement_element_ids"
            )
        missing_replacements = [value for value in replacement_ids if value not in elements]
        if missing_replacements:
            raise ValueError(
                f"Annotation occlusion mask {identifier} references missing replacement elements: "
                + ", ".join(missing_replacements)
            )
        if not any(elements[value].get("type") in {"text", "text_path"} for value in replacement_ids):
            raise ValueError(
                f"Annotation occlusion mask {identifier} requires at least one live-text replacement"
            )
        canvas_rect = map_atomic_source_rect_to_canvas(rect, atomic)
        strict_image_rect(canvas_rect, canvas_size, label=f"annotation_occlusion_masks[{identifier}]")
        intersections = [
            region["id"]
            for region in protected
            if rectangles_intersect(canvas_rect, region["rect_px"])
        ]
        if intersections:
            raise ValueError(
                f"Annotation occlusion mask {identifier} intersects protected scientific pixels: "
                + ", ".join(intersections)
            )


def validate_recipe(recipe: dict, source_size: tuple[int, int] | None = None) -> None:
    schema = load_schema()
    missing = [key for key in schema["required"] if key not in recipe]
    if missing:
        raise ValueError(f"Recipe is missing required fields: {', '.join(missing)}")
    recovery_levels = set(schema["properties"]["recovery_level"]["enum"])
    if recipe["recovery_level"] not in recovery_levels:
        raise ValueError("Unsupported recovery_level")
    canvas_size = validate_canvas(recipe, source_size)
    validate_masks(recipe, canvas_size, schema)
    gradient_ids = validate_gradients(recipe)
    graphic_ids = validate_elements(recipe, schema, gradient_ids)
    reserved_ids = graphic_ids | {
        "page-background",
        "raster-base",
        "vector-overlay",
        "annotation-occlusion-masks",
        "cleaned-source",
    }
    validate_raster_regions(recipe, canvas_size, reserved_ids)
    validate_atomic_rasters(recipe, canvas_size, reserved_ids)
    validate_annotation_occlusion_masks(recipe, canvas_size, reserved_ids)
    if recipe.get("contract", {}).get("require_zero_rasters") and (
        recipe.get("raster_regions") or recipe.get("atomic_rasters")
    ):
        raise ValueError("require_zero_rasters forbids raster_regions and atomic_rasters")


def nearest_non_red_color(
    image: Image.Image,
    x: int,
    y: int,
    config: ColorRemovalConfig,
) -> tuple[int, int, int] | None:
    neighbors = []
    for yy in range(max(0, y - config.radius), min(image.height, y + config.radius + 1)):
        for xx in range(max(0, x - config.radius), min(image.width, x + config.radius + 1)):
            sample = image.getpixel((xx, yy))
            if not is_remove_color(sample, config.red_min, config.dominance_min):
                neighbors.append(sample)
    if not neighbors:
        return None
    median_color = tuple(round(statistics.median(channel)) for channel in zip(*neighbors))
    return min(
        neighbors,
        key=lambda color: sum((color[index] - median_color[index]) ** 2 for index in range(3)),
    )


def remove_selected_color(image: Image.Image, target: PixelRect, config: ColorRemovalConfig) -> None:
    original = image.copy()
    for y in range(target[1], target[3]):
        for x in range(target[0], target[2]):
            if not is_remove_color(original.getpixel((x, y)), config.red_min, config.dominance_min):
                continue
            replacement = nearest_non_red_color(original, x, y, config)
            if replacement is not None:
                image.putpixel((x, y), replacement)


def apply_mask(image: Image.Image, mask: dict) -> None:
    mode = mask.get("mode", "fill")
    target = image_rect(mask["rect_px"], image.size)
    if mode == "fill":
        ImageDraw.Draw(image).rectangle(target, fill=ImageColor.getrgb(mask.get("color", "#ffffff")))
        return
    if mode == "sample":
        sample_x, sample_y = mask["sample_px"]
        ImageDraw.Draw(image).rectangle(target, fill=image.getpixel((round(sample_x), round(sample_y))))
        return
    if mode == "clone":
        source_rect = image_rect(mask["source_rect_px"], image.size)
        patch = image.crop(source_rect).resize((target[2] - target[0], target[3] - target[1]))
        image.paste(patch, target)
        return
    if mode == "color_remove":
        config = ColorRemovalConfig(
            red_min=int(mask.get("red_min", 140)),
            dominance_min=int(mask.get("dominance_min", 8)),
            radius=int(mask.get("radius", 10)),
        )
        remove_selected_color(image, target, config)
        return
    raise ValueError(f"Unsupported mask mode: {mode}")


def clean_raster(source: Path, masks: list[dict], output: Path, overwrite: bool = False) -> Image.Image:
    require_new_output(output, overwrite)
    opened = Image.open(source)
    if opened.mode not in {"RGB", "RGBA"}:
        raise ValueError(
            f"Source mode {opened.mode} cannot be converted silently; normalize a reviewed copy to RGB/RGBA first"
        )
    icc_profile = opened.info.get("icc_profile")
    image = opened.copy()
    opened.close()
    for mask in masks:
        apply_mask(image, mask)
    output.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        suffix=".png", prefix=f".{output.stem}-", dir=output.parent, delete=False
    )
    temporary = Path(handle.name)
    handle.close()
    try:
        save_args = {"format": "PNG", "optimize": True}
        if icc_profile:
            save_args["icc_profile"] = icc_profile
        image.save(temporary, **save_args)
        os.replace(temporary, output)
    finally:
        if temporary.exists():
            temporary.unlink()
    return image


def data_uri(path: Path) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def crop_data_uri(image: Image.Image, source_rect: list[float]) -> str:
    crop = image.crop(image_rect(source_rect, image.size))
    buffer = io.BytesIO()
    crop.save(buffer, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def normalized_pixel_digest(image: Image.Image) -> str:
    normalized = image.convert("RGBA")
    digest = hashlib.sha256()
    digest.update(f"{normalized.width}x{normalized.height}:RGBA\0".encode("ascii"))
    digest.update(normalized.tobytes())
    return digest.hexdigest()


def bbox_metadata(box: list[float]) -> str:
    return ",".join(f"{float(value):g}" for value in box)


def raster_metadata(region: dict) -> str:
    values = {
        "data-raster-reason": region["raster_reason"],
        "data-atomic-raster-unit": str(bool(region["atomic_raster_unit"])).lower(),
        "data-contains-reconstructable-content": str(
            bool(region["contains_reconstructable_content"])
        ).lower(),
        "data-decomposition-note": region["decomposition_note"],
        "data-evidence": str(bool(region.get("evidence", False))).lower(),
        "data-nonuniform-scale": "false",
        "data-source-bbox-px": bbox_metadata(region["source_bbox_px"]),
        "data-canvas-bbox-px": bbox_metadata(region["canvas_bbox_px"]),
    }
    return " ".join(f'{key}="{html.escape(str(value))}"' for key, value in values.items())


def resolve_atomic_asset(
    raw: str,
    *,
    recipe_dir: Path | None,
    fallbacks: tuple[Path, ...],
) -> Path:
    requested = Path(raw)
    candidates = []
    if requested.is_absolute():
        candidates.append(requested)
    if recipe_dir is not None:
        candidates.append(recipe_dir / requested)
    candidates.extend(path for path in fallbacks if raw in {path.name, str(path)})
    candidates.append(Path.cwd() / requested)
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.exists() and resolved.is_file():
            return workspace_path(str(resolved), must_exist=True)
    raise FileNotFoundError(f"Atomic raster asset does not exist: {raw}")


def normalized_legacy_raster(region: dict) -> dict:
    source_box = region["source_rect_px"]
    canvas_box = region.get("dest_rect_px", source_box)
    is_atomic = bool(region["atomic_raster_unit"])
    return {
        **region,
        "source_bbox_px": source_box,
        "canvas_bbox_px": canvas_box,
        "evidence": is_atomic and not bool(region["contains_reconstructable_content"]),
    }


def render_raster_images(
    recipe: dict,
    source: Path,
    cleaned: Path,
    context: RasterRenderContext,
    recipe_dir: Path | None = None,
) -> list[str]:
    atomic_regions = recipe.get("atomic_rasters", [])
    legacy_regions = recipe.get("raster_regions", [])
    if recipe.get("contract", {}).get("require_zero_rasters"):
        return []
    if not atomic_regions and not legacy_regions:
        fallback = {
            "raster_reason": "Undecomposed hybrid prototype base",
            "atomic_raster_unit": False,
            "contains_reconstructable_content": True,
            "decomposition_note": "Split into atomic evidence fields before final delivery.",
            "evidence": False,
            "source_bbox_px": [0, 0, context.width_user, context.height_user],
            "canvas_bbox_px": [0, 0, context.width_user, context.height_user],
        }
        return [
            f'<image id="cleaned-source" data-source-file="{html.escape(source.name)}" '
            f'data-cleaned-file="{html.escape(cleaned.name)}" '
            f'{raster_metadata(fallback)} xlink:href="{data_uri(cleaned)}" x="0" y="0" '
            f'width="{context.width_user:.4f}" height="{context.height_user:.4f}" '
            f'preserveAspectRatio="none"/>'
        ]
    rendered = []
    if atomic_regions:
        masks_by_atomic: dict[str, list[dict]] = {}
        for mask in recipe.get("annotation_occlusion_masks", []):
            masks_by_atomic.setdefault(mask["atomic_raster_id"], []).append(mask)
        for region in atomic_regions:
            source_asset = resolve_atomic_asset(
                region["source_file"], recipe_dir=recipe_dir, fallbacks=(source,)
            )
            cleaned_asset = resolve_atomic_asset(
                region["cleaned_file"], recipe_dir=recipe_dir, fallbacks=(cleaned, source)
            )
            with Image.open(source_asset) as source_image, Image.open(cleaned_asset) as image:
                if source_image.size != image.size:
                    raise ValueError(
                        f"Atomic raster {region['id']} source_file and cleaned_file dimensions differ"
                    )
                crop_rect = strict_image_rect(
                    region["source_bbox_px"], image.size, label=f"atomic_rasters[{region['id']}].source_bbox_px"
                )
                source_crop = source_image.crop(crop_rect)
                cleaned_crop = image.crop(crop_rect)
                source_digest = normalized_pixel_digest(source_crop)
                cleaned_digest = normalized_pixel_digest(cleaned_crop)
                if masks_by_atomic.get(region["id"]) and source_digest != cleaned_digest:
                    raise ValueError(
                        f"Atomic raster {region['id']} violates source_pixels_immutable: "
                        "source and cleaned crops differ"
                    )
                for mask in masks_by_atomic.get(region["id"], []):
                    if mask["source_crop_sha256"] != source_digest:
                        raise ValueError(
                            f"Annotation occlusion mask {mask['id']} source_crop_sha256 "
                            f"does not match atomic raster {region['id']}"
                        )
                if crop_rect == (0, 0, image.width, image.height):
                    raise ValueError(f"Atomic raster {region['id']} cannot embed its whole source image")
                destination = region["canvas_bbox_px"]
                normalized = {
                    **region,
                    "atomic_raster_unit": True,
                    "contains_reconstructable_content": False,
                }
                x, y, width, height = destination
                rendered.append(
                    f'<image id="{html.escape(region["id"])}" '
                    f'data-source-file="{html.escape(source_asset.name)}" '
                    f'data-cleaned-file="{html.escape(cleaned_asset.name)}" '
                    f'data-source-crop-sha256="{source_digest}" '
                    f'data-embedded-crop-sha256="{cleaned_digest}" '
                    f'{raster_metadata(normalized)} '
                    f'xlink:href="{crop_data_uri(image, region["source_bbox_px"])}" '
                    f'x="{context.px(x)}" y="{context.px(y)}" width="{context.px(width)}" '
                    f'height="{context.px(height)}" preserveAspectRatio="xMidYMid meet"/>'
                )
        return rendered
    with Image.open(cleaned) as image:
        for legacy_region in legacy_regions:
            region = normalized_legacy_raster(legacy_region)
            destination = region["canvas_bbox_px"]
            x, y, width, height = destination
            rendered.append(
                f'<image id="{html.escape(region["id"])}" data-source-file="{html.escape(source.name)}" '
                f'data-cleaned-file="{html.escape(cleaned.name)}" '
                f'{raster_metadata(region)} '
                f'xlink:href="{crop_data_uri(image, region["source_bbox_px"])}" '
                f'x="{context.px(x)}" y="{context.px(y)}" width="{context.px(width)}" '
                f'height="{context.px(height)}" '
                f'preserveAspectRatio="xMidYMid meet"/>'
            )
    return rendered


def render_annotation_occlusion_masks(recipe: dict, px) -> list[str]:
    masks = recipe.get("annotation_occlusion_masks", [])
    if not masks:
        return []
    atomic_by_id = {region["id"]: region for region in recipe.get("atomic_rasters", [])}
    rendered = ['<g id="annotation-occlusion-masks" aria-label="Audited annotation occlusion masks">']
    for mask in masks:
        canvas_rect = map_atomic_source_rect_to_canvas(
            mask["rect_px"], atomic_by_id[mask["atomic_raster_id"]]
        )
        x, y, width, height = canvas_rect
        replacements = ",".join(mask["replacement_element_ids"])
        rendered.append(
            f'<rect id="{html.escape(mask["id"])}" x="{px(x)}" y="{px(y)}" '
            f'width="{px(width)}" height="{px(height)}" '
            f'fill="{html.escape(mask["fill"])}" stroke="none" '
            f'data-atomic-raster-id="{html.escape(mask["atomic_raster_id"])}" '
            f'data-source-rect-px="{bbox_metadata(mask["rect_px"])}" '
            f'data-occlusion-mode="{html.escape(mask["mode"])}" '
            f'data-max-area-fraction="{float(mask["max_area_fraction"]):g}" '
            f'data-evidence-change-contract="source_pixels_immutable" '
            f'data-source-crop-sha256="{html.escape(mask["source_crop_sha256"])}" '
            f'data-old-annotation-risk="{html.escape(mask["old_annotation_risk"])}" '
            f'data-approval-status="{html.escape(mask["approval_status"])}" '
            f'data-approved-by="{html.escape(str(mask.get("approved_by", "")))}" '
            f'data-approval-note="{html.escape(str(mask.get("approval_note", "")))}" '
            f'data-replacement-element-ids="{html.escape(replacements)}"/>'
        )
    rendered.append("</g>")
    return rendered


def text_style(element: dict, defaults: dict) -> str:
    family = element.get("font_family", defaults.get("font_family", "Times New Roman"))
    size_pt = float(element.get("font_size_pt", defaults.get("font_size_pt", 8.5)))
    size_px = size_pt * CSS_PX_PER_PT
    fill = element.get("fill", defaults.get("text_fill", "#000000"))
    weight = element.get("font_weight", "normal")
    style = element.get("font_style", "normal")
    return (
        f'font-family="{html.escape(str(family))}" font-size="{size_px:.6f}px" '
        f'fill="{html.escape(str(fill))}" font-weight="{html.escape(str(weight))}" '
        f'font-style="{html.escape(str(style))}"'
    )


def stroke_width_pt(element: dict, defaults: dict) -> float:
    explicit = float(element.get("stroke_width_pt", 0))
    if explicit:
        return explicit
    return float(element.get("stroke_width_mm", defaults.get("stroke_width_mm", 0.2))) * PT_PER_MM


def fill_value(element: dict) -> str:
    if element.get("fill_gradient"):
        return f'url(#{html.escape(str(element["fill_gradient"]))})'
    return html.escape(str(element.get("fill", "none")))


def render_text_content(element: dict) -> str:
    if element.get("runs"):
        rendered_runs = []
        for run in element["runs"]:
            attributes = []
            baseline = run.get("baseline_shift")
            if baseline:
                attributes.append(f'baseline-shift="{html.escape(str(baseline))}"')
            if "font_size_percent" in run:
                attributes.append(f'font-size="{float(run["font_size_percent"]):g}%"')
            if "font_style" in run:
                attributes.append(f'font-style="{html.escape(str(run["font_style"]))}"')
            attribute_text = (" " + " ".join(attributes)) if attributes else ""
            rendered_runs.append(
                f'<tspan{attribute_text}>{html.escape(str(run.get("text", "")))}</tspan>'
            )
        return "".join(rendered_runs)
    return html.escape(str(element["text"]))


def render_text(element: dict, element_id: str, px, defaults: dict) -> str:
    x = px(element["x_px"])
    y = px(element["y_px"])
    anchor = html.escape(element.get("anchor", "start"))
    rotation = float(element.get("rotation_deg", 0))
    transform = f' transform="rotate({rotation:g} {x} {y})"' if rotation else ""
    text_value = render_text_content(element)
    return (
        f'<text id="{element_id}" x="{x}" y="{y}" text-anchor="{anchor}" '
        f'{text_style(element, defaults)}{transform}>{text_value}</text>'
    )


def render_line(element: dict, element_id: str, px, defaults: dict) -> str:
    width_px = stroke_width_pt(element, defaults) * CSS_PX_PER_PT
    dash = element.get("dash_mm")
    dash_attr = ""
    if dash:
        dash_attr = ' stroke-dasharray="' + " ".join(
            f"{float(value) * PT_PER_MM * CSS_PX_PER_PT:.4f}px" for value in dash
        ) + '"'
    return (
        f'<line id="{element_id}" x1="{px(element["x1_px"])}" y1="{px(element["y1_px"])}" '
        f'x2="{px(element["x2_px"])}" y2="{px(element["y2_px"])}" '
        f'stroke="{html.escape(element.get("stroke", "#000000"))}" '
        f'stroke-width="{width_px:.4f}px" '
        f'stroke-linecap="{html.escape(element.get("linecap", "butt"))}"{dash_attr}/>'
    )


def render_rect(element: dict, element_id: str, px, defaults: dict) -> str:
    width_px = stroke_width_pt(element, defaults) * CSS_PX_PER_PT
    return (
        f'<rect id="{element_id}" x="{px(element["x_px"])}" y="{px(element["y_px"])}" '
        f'width="{px(element["width_px"])}" height="{px(element["height_px"])}" '
        f'fill="{fill_value(element)}" '
        f'stroke="{html.escape(element.get("stroke", "#000000"))}" '
        f'stroke-width="{width_px:.4f}px"/>'
    )


def render_ellipse(element: dict, element_id: str, px, defaults: dict) -> str:
    width_px = stroke_width_pt(element, defaults) * CSS_PX_PER_PT
    return (
        f'<ellipse id="{element_id}" cx="{px(element["cx_px"])}" cy="{px(element["cy_px"])}" '
        f'rx="{px(element["rx_px"])}" ry="{px(element["ry_px"])}" '
        f'fill="{fill_value(element)}" '
        f'stroke="{html.escape(element.get("stroke", "#000000"))}" '
        f'stroke-width="{width_px:.4f}px"/>'
    )


def render_polyline(element: dict, element_id: str, px, defaults: dict) -> str:
    points = " ".join(f"{px(point[0])},{px(point[1])}" for point in element["points_px"])
    width_px = stroke_width_pt(element, defaults) * CSS_PX_PER_PT
    return (
        f'<polyline id="{element_id}" points="{points}" fill="{fill_value(element)}" '
        f'stroke="{html.escape(element.get("stroke", "#000000"))}" '
        f'stroke-width="{width_px:.4f}px"/>'
    )


def path_styling(element: dict, defaults: dict, *, default_fill: str = "none") -> str:
    width_px = stroke_width_pt(element, defaults) * CSS_PX_PER_PT
    dash = element.get("dash_mm")
    dash_attr = ""
    if dash:
        dash_attr = ' stroke-dasharray="' + " ".join(
            f"{float(value) * PT_PER_MM * CSS_PX_PER_PT:.4f}px" for value in dash
        ) + '"'
    fill = fill_value(element) if "fill" in element or element.get("fill_gradient") else default_fill
    return (
        f'fill="{fill}" stroke="{html.escape(str(element.get("stroke", "#000000")))}" '
        f'stroke-width="{width_px:.4f}px" '
        f'stroke-linecap="{html.escape(str(element.get("linecap", "butt")))}" '
        f'stroke-linejoin="{html.escape(str(element.get("linejoin", "miter")))}"{dash_attr}'
    )


def render_polygon(element: dict, element_id: str, px, defaults: dict) -> str:
    points = " ".join(f"{px(point[0])},{px(point[1])}" for point in element["points_px"])
    return f'<polygon id="{element_id}" points="{points}" {path_styling(element, defaults)}/>'


def render_path_commands(commands: list[dict], px) -> str:
    rendered = []
    for command in commands:
        operation = command["op"]
        if operation in {"M", "L"}:
            rendered.append(f'{operation} {px(command["x_px"])} {px(command["y_px"])}')
        elif operation == "C":
            rendered.append(
                f'C {px(command["x1_px"])} {px(command["y1_px"])} '
                f'{px(command["x2_px"])} {px(command["y2_px"])} '
                f'{px(command["x_px"])} {px(command["y_px"])}'
            )
        elif operation == "Q":
            rendered.append(
                f'Q {px(command["x1_px"])} {px(command["y1_px"])} '
                f'{px(command["x_px"])} {px(command["y_px"])}'
            )
        elif operation == "A":
            rendered.append(
                f'A {px(command["rx_px"])} {px(command["ry_px"])} '
                f'{float(command["x_axis_rotation_deg"]):g} '
                f'{int(bool(command["large_arc"]))} {int(bool(command["sweep"]))} '
                f'{px(command["x_px"])} {px(command["y_px"])}'
            )
        else:
            rendered.append("Z")
    return " ".join(rendered)


def render_path(element: dict, element_id: str, px, defaults: dict) -> str:
    path_data = render_path_commands(element["commands"], px)
    return f'<path id="{element_id}" d="{path_data}" {path_styling(element, defaults)}/>'


def point_on_circle(cx: float, cy: float, radius: float, angle_deg: float) -> tuple[float, float]:
    radians = math.radians(angle_deg)
    return cx + radius * math.cos(radians), cy + radius * math.sin(radians)


def arc_delta(start_angle: float, end_angle: float, clockwise: bool) -> float:
    raw = (end_angle - start_angle) if clockwise else (start_angle - end_angle)
    delta = raw % 360.0
    return 360.0 if math.isclose(delta, 0.0, abs_tol=1e-9) else delta


def circular_arc_path(
    cx: float,
    cy: float,
    radius: float,
    start_angle: float,
    end_angle: float,
    clockwise: bool,
    px,
) -> str:
    delta = arc_delta(start_angle, end_angle, clockwise)
    sweep = 1 if clockwise else 0
    start = point_on_circle(cx, cy, radius, start_angle)
    if math.isclose(delta, 360.0, abs_tol=1e-9):
        midpoint_angle = start_angle + (180.0 if clockwise else -180.0)
        midpoint = point_on_circle(cx, cy, radius, midpoint_angle)
        return (
            f'M {px(start[0])} {px(start[1])} '
            f'A {px(radius)} {px(radius)} 0 0 {sweep} {px(midpoint[0])} {px(midpoint[1])} '
            f'A {px(radius)} {px(radius)} 0 0 {sweep} {px(start[0])} {px(start[1])}'
        )
    end = point_on_circle(cx, cy, radius, end_angle)
    large_arc = 1 if delta > 180.0 else 0
    return (
        f'M {px(start[0])} {px(start[1])} '
        f'A {px(radius)} {px(radius)} 0 {large_arc} {sweep} {px(end[0])} {px(end[1])}'
    )


def render_arc(element: dict, element_id: str, px, defaults: dict) -> str:
    path_data = circular_arc_path(
        float(element["cx_px"]),
        float(element["cy_px"]),
        float(element["radius_px"]),
        float(element["start_angle_deg"]),
        float(element["end_angle_deg"]),
        bool(element.get("clockwise", True)),
        px,
    )
    return f'<path id="{element_id}" d="{path_data}" {path_styling(element, defaults)}/>'


def render_annular_sector(element: dict, element_id: str, px, defaults: dict) -> str:
    cx = float(element["cx_px"])
    cy = float(element["cy_px"])
    inner = float(element["inner_radius_px"])
    outer = float(element["outer_radius_px"])
    start_angle = float(element["start_angle_deg"])
    end_angle = float(element["end_angle_deg"])
    clockwise = bool(element.get("clockwise", True))
    delta = arc_delta(start_angle, end_angle, clockwise)
    if math.isclose(delta, 360.0, abs_tol=1e-9):
        outer_path = circular_arc_path(cx, cy, outer, start_angle, end_angle, clockwise, px)
        inner_path = circular_arc_path(cx, cy, inner, start_angle, end_angle, not clockwise, px)
        path_data = f'{outer_path} {inner_path} Z'
    else:
        sweep = 1 if clockwise else 0
        reverse_sweep = 0 if clockwise else 1
        large_arc = 1 if delta > 180.0 else 0
        outer_start = point_on_circle(cx, cy, outer, start_angle)
        outer_end = point_on_circle(cx, cy, outer, end_angle)
        inner_end = point_on_circle(cx, cy, inner, end_angle)
        inner_start = point_on_circle(cx, cy, inner, start_angle)
        path_data = (
            f'M {px(outer_start[0])} {px(outer_start[1])} '
            f'A {px(outer)} {px(outer)} 0 {large_arc} {sweep} {px(outer_end[0])} {px(outer_end[1])} '
            f'L {px(inner_end[0])} {px(inner_end[1])} '
            f'A {px(inner)} {px(inner)} 0 {large_arc} {reverse_sweep} {px(inner_start[0])} {px(inner_start[1])} Z'
        )
    return f'<path id="{element_id}" d="{path_data}" {path_styling(element, defaults)}/>'


def render_text_path(element: dict, element_id: str, px, defaults: dict) -> str:
    curve_id = f"{element_id}__curve"
    path_data = circular_arc_path(
        float(element["cx_px"]),
        float(element["cy_px"]),
        float(element["radius_px"]),
        float(element["start_angle_deg"]),
        float(element["end_angle_deg"]),
        bool(element.get("clockwise", True)),
        px,
    )
    anchor = html.escape(str(element.get("anchor", "middle")))
    offset = float(element.get("start_offset_percent", 50))
    return (
        f'<path id="{curve_id}" d="{path_data}" fill="none" stroke="none"/>'
        f'<text id="{element_id}" text-anchor="{anchor}" {text_style(element, defaults)}>'
        f'<textPath xlink:href="#{curve_id}" startOffset="{offset:g}%">'
        f'{render_text_content(element)}</textPath></text>'
    )


def render_group(element: dict, element_id: str, px, defaults: dict) -> str:
    children = "".join(
        render_element(child, index, px, defaults)
        for index, child in enumerate(element["children"], start=1)
    )
    label = element.get("aria_label")
    label_attr = f' aria-label="{html.escape(str(label))}"' if label else ""
    return f'<g id="{element_id}"{label_attr}>{children}</g>'


def render_gradient_definitions(recipe: dict, px) -> list[str]:
    gradients = recipe.get("gradients", [])
    if not gradients:
        return []
    rendered = ["<defs>"]
    for gradient in gradients:
        gradient_id = html.escape(str(gradient["id"]))
        if gradient["type"] == "linear":
            rendered.append(
                f'<linearGradient id="{gradient_id}" gradientUnits="userSpaceOnUse" '
                f'x1="{px(gradient["x1_px"])}" y1="{px(gradient["y1_px"])}" '
                f'x2="{px(gradient["x2_px"])}" y2="{px(gradient["y2_px"])}">'
            )
        else:
            fx = gradient.get("fx_px", gradient["cx_px"])
            fy = gradient.get("fy_px", gradient["cy_px"])
            rendered.append(
                f'<radialGradient id="{gradient_id}" gradientUnits="userSpaceOnUse" '
                f'cx="{px(gradient["cx_px"])}" cy="{px(gradient["cy_px"])}" '
                f'r="{px(gradient["radius_px"])}" fx="{px(fx)}" fy="{px(fy)}">'
            )
        for stop in gradient["stops"]:
            opacity = (
                f' stop-opacity="{float(stop["opacity"]):g}"' if "opacity" in stop else ""
            )
            rendered.append(
                f'<stop offset="{float(stop["offset_percent"]):g}%" '
                f'stop-color="{html.escape(str(stop["color"]))}"{opacity}/>'
            )
        rendered.append("</linearGradient>" if gradient["type"] == "linear" else "</radialGradient>")
    rendered.append("</defs>")
    return rendered


def render_element(element: dict, index: int, px, defaults: dict) -> str:
    kind = element["type"]
    element_id = html.escape(element.get("id", f"{kind}-{index}"))
    renderers = {
        "text": render_text,
        "line": render_line,
        "rect": render_rect,
        "ellipse": render_ellipse,
        "polyline": render_polyline,
        "polygon": render_polygon,
        "path": render_path,
        "arc": render_arc,
        "annular_sector": render_annular_sector,
        "group": render_group,
        "text_path": render_text_path,
    }
    if kind not in renderers:
        raise ValueError(f"Unsupported element type: {kind}")
    return renderers[kind](element, element_id, px, defaults)


def build_svg(
    recipe: dict,
    source: Path,
    cleaned: Path,
    output: Path,
    overwrite: bool = False,
    *,
    recipe_dir: Path | None = None,
) -> None:
    with Image.open(source) as source_image:
        source_size = source_image.size
    validate_recipe(recipe, source_size)
    canvas = recipe["canvas"]
    width_px = int(canvas.get("width_px") or source_size[0])
    height_px = int(canvas.get("height_px") or source_size[1])
    if source_size != (width_px, height_px):
        raise ValueError(f"Recipe canvas {width_px}x{height_px} does not match source {source_size}")
    print_width_mm = float(canvas["print_width_mm"])
    print_height_mm = print_width_mm * height_px / width_px
    width_user = print_width_mm * CSS_PX_PER_MM
    scale = width_user / width_px
    height_user = height_px * scale
    defaults = recipe.get("defaults", {})

    def px(value: float) -> str:
        return f"{float(value) * scale:.4f}"

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'width="{print_width_mm:.4f}mm" height="{print_height_mm:.4f}mm" '
            f'viewBox="0 0 {width_user:.4f} {height_user:.4f}">'
        ),
        f'<title>{html.escape(recipe.get("title", output.stem))}</title>',
    ]

    parts.extend(render_gradient_definitions(recipe, px))
    background_fill = str(canvas.get("background_fill", "#ffffff")).strip()
    if background_fill.lower() != "none":
        parts.append(
            f'<rect id="page-background" x="0" y="0" width="{width_user:.4f}" '
            f'height="{height_user:.4f}" fill="{html.escape(background_fill)}"/>'
        )
    parts.append('<g id="raster-base" aria-label="Cleaned raster base">')

    raster_context = RasterRenderContext(px=px, width_user=width_user, height_user=height_user)
    parts.extend(render_raster_images(recipe, source, cleaned, raster_context, recipe_dir))
    parts.extend(['</g>', '<g id="vector-overlay" aria-label="Editable vector overlay">'])
    parts.extend(render_annotation_occlusion_masks(recipe, px))

    parts.extend(
        render_element(element, index, px, defaults)
        for index, element in enumerate(recipe.get("elements", []), start=1)
    )

    parts.extend(["</g>", "</svg>"])
    atomic_write_text(output, "\n".join(parts) + "\n", overwrite)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a cleaned-raster plus editable-vector SVG from a JSON recipe.")
    parser.add_argument("recipe", type=lambda raw: workspace_path(raw, must_exist=True))
    parser.add_argument("output_svg", type=workspace_path)
    parser.add_argument("--cleaned-image", type=workspace_path)
    parser.add_argument("--force", action="store_true", help="Replace generated outputs explicitly.")
    args = parser.parse_args()

    recipe_path = args.recipe
    recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
    source = Path(recipe["source_image"])
    if not source.is_absolute():
        source = recipe_path.parent / source
    source = workspace_path(str(source), must_exist=True)
    output = args.output_svg
    cleaned = args.cleaned_image if args.cleaned_image else output.with_name(output.stem + "_cleaned.png")
    with Image.open(source) as source_image:
        validate_recipe(recipe, source_image.size)
    require_new_output(output, args.force)
    if recipe.get("contract", {}).get("require_zero_rasters"):
        build_svg(recipe, source, source, output, args.force, recipe_dir=recipe_path.parent)
    elif recipe.get("atomic_rasters"):
        build_svg(recipe, source, source, output, args.force, recipe_dir=recipe_path.parent)
    else:
        require_new_output(cleaned, args.force)
        clean_raster(source, recipe.get("masks", []), cleaned, args.force)
        build_svg(recipe, source, cleaned, output, args.force, recipe_dir=recipe_path.parent)
        print(f"cleaned_image={cleaned}")
    print(f"editable_svg={output}")


if __name__ == "__main__":
    main()
