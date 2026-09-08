#!/usr/bin/env python3
"""Build publication-size, Illustrator-friendly multi-panel line charts.

The renderer intentionally emits plain SVG primitives and live ``<text>``
objects.  It does not use canvas, foreignObject, filters, remote resources, or
text outlines.  All dimensions are derived from a physical canvas so an
Illustrator audit can verify the requested point size and stroke width.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
from pathlib import Path
from typing import Any


PT_TO_MM = 25.4 / 72.0


def fail(message: str) -> None:
    raise ValueError(message)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        fail("Recipe root must be an object")
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def number(value: Any, name: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must be numeric") from error
    if not math.isfinite(result):
        fail(f"{name} must be finite")
    return result


def read_rows(path: Path) -> list[dict[str, float]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            fail("CSV has no header")
        rows: list[dict[str, float]] = []
        for row_index, row in enumerate(reader, start=2):
            parsed: dict[str, float] = {}
            for key, raw in row.items():
                parsed[key] = number(raw, f"CSV row {row_index} column {key}")
            rows.append(parsed)
    if len(rows) < 2:
        fail("CSV must contain at least two rows")
    return rows


def fmt(value: float) -> str:
    return f"{value:.4f}".rstrip("0").rstrip(".")


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def point_series(
    rows: list[dict[str, float]],
    x_key: str,
    y_key: str,
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
    plot: dict[str, float],
) -> str:
    points: list[str] = []
    previous_x = -math.inf
    for row in rows:
        x_value = row[x_key]
        y_value = row[y_key]
        if x_value < previous_x:
            fail(f"Data column {x_key} must be monotonic")
        previous_x = x_value
        if not (x_min <= x_value <= x_max):
            fail(f"Data value {x_value} lies outside x range")
        if not (y_min <= y_value <= y_max):
            fail(f"Data value {y_value} lies outside y range")
        x = plot["x"] + (x_value - x_min) / (x_max - x_min) * plot["width"]
        y = plot["y"] + plot["height"] - (y_value - y_min) / (y_max - y_min) * plot["height"]
        points.append(f"{fmt(x)},{fmt(y)}")
    return " ".join(points)


def text_element(
    element_id: str,
    x: float,
    y: float,
    value: str,
    font_size: float,
    anchor: str = "middle",
    transform: str | None = None,
) -> str:
    transform_attr = f' transform="{esc(transform)}"' if transform else ""
    return (
        f'<text id="{esc(element_id)}" x="{fmt(x)}" y="{fmt(y)}" '
        f'text-anchor="{anchor}" class="live-text" font-size="{fmt(font_size)}"'
        f'{transform_attr}>{esc(value)}</text>'
    )


def validate_recipe(recipe: dict[str, Any], recipe_path: Path) -> tuple[Path, list[dict[str, float]]]:
    canvas = recipe.get("canvas", {})
    for key in ("width_units", "height_units", "width_mm", "height_mm"):
        if number(canvas.get(key), f"canvas.{key}") <= 0:
            fail(f"canvas.{key} must be positive")
    if len(recipe.get("panels", [])) < 1:
        fail("Recipe must contain at least one panel")
    data = recipe.get("data", {})
    source = (recipe_path.parent / str(data.get("csv", ""))).resolve()
    if not source.is_file():
        fail(f"CSV does not exist: {source}")
    expected_hash = str(data.get("sha256", "")).lower()
    if expected_hash and sha256(source).lower() != expected_hash:
        fail("CSV SHA-256 does not match recipe")
    rows = read_rows(source)
    expected_rows = int(data.get("row_count", len(rows)))
    if len(rows) != expected_rows:
        fail(f"Expected {expected_rows} data rows, got {len(rows)}")
    return source, rows


def render(recipe: dict[str, Any], recipe_path: Path) -> str:
    source, rows = validate_recipe(recipe, recipe_path)
    canvas = recipe["canvas"]
    width_units = number(canvas["width_units"], "canvas.width_units")
    height_units = number(canvas["height_units"], "canvas.height_units")
    width_mm = number(canvas["width_mm"], "canvas.width_mm")
    height_mm = number(canvas["height_mm"], "canvas.height_mm")
    units_per_mm_x = width_units / width_mm
    units_per_mm_y = height_units / height_mm
    if abs(units_per_mm_x - units_per_mm_y) > 1e-6:
        fail("Canvas must use one isotropic physical scale")
    units_per_mm = units_per_mm_x

    typography = recipe["typography"]
    font_size_pt = number(typography["size_pt"], "typography.size_pt")
    font_size = font_size_pt * PT_TO_MM * units_per_mm
    axis_stroke = number(recipe["strokes"]["axis_mm"], "strokes.axis_mm") * units_per_mm
    grid_stroke = number(recipe["strokes"]["grid_mm"], "strokes.grid_mm") * units_per_mm
    curve_stroke = number(recipe["strokes"]["curve_mm"], "strokes.curve_mm") * units_per_mm

    output: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{fmt(width_mm)}mm" '
            f'height="{fmt(height_mm)}mm" viewBox="0 0 {fmt(width_units)} {fmt(height_units)}">'
        ),
        f'<title>{esc(recipe.get("title", "Editable line chart"))}</title>',
        '<metadata>',
        esc(json.dumps({
            "source_csv": str(source),
            "source_sha256": sha256(source),
            "font_size_pt": font_size_pt,
            "axis_stroke_mm": number(recipe["strokes"]["axis_mm"], "strokes.axis_mm"),
            "recovery_level": recipe.get("recovery_level"),
        }, ensure_ascii=False, sort_keys=True)),
        '</metadata>',
        '<style>',
        (
            ".live-text{font-family:'Times New Roman';font-weight:normal;fill:#111111;}"
            ".axis{fill:none;stroke:#111111;stroke-linejoin:miter;}"
            ".grid{stroke:#b9c9cc;fill:none;}"
            ".curve{fill:none;stroke-linejoin:round;stroke-linecap:round;}"
        ),
        '</style>',
        f'<rect id="page-background" x="0" y="0" width="{fmt(width_units)}" height="{fmt(height_units)}" fill="#ffffff"/>',
    ]

    x_key = str(recipe["data"]["x_column"])
    for panel in recipe["panels"]:
        panel_id = str(panel["id"])
        plot = {key: number(panel["plot"][key], f"{panel_id}.plot.{key}") for key in ("x", "y", "width", "height")}
        x_min, x_max = [number(value, f"{panel_id}.x_range") for value in panel["x_range"]]
        y_min, y_max = [number(value, f"{panel_id}.y_range") for value in panel["y_range"]]
        if x_max <= x_min or y_max <= y_min:
            fail(f"Panel {panel_id} has an invalid range")
        output.append(f'<g id="{esc(panel_id)}" aria-label="{esc(panel["caption"])}">')

        for index, tick_raw in enumerate(panel["x_ticks"]):
            tick = number(tick_raw, f"{panel_id}.x_ticks")
            x = plot["x"] + (tick - x_min) / (x_max - x_min) * plot["width"]
            if tick != x_min and tick != x_max:
                output.append(
                    f'<line id="{esc(panel_id)}-x-grid-{index}" class="grid" x1="{fmt(x)}" y1="{fmt(plot["y"])}" '
                    f'x2="{fmt(x)}" y2="{fmt(plot["y"] + plot["height"])}" stroke-width="{fmt(grid_stroke)}"/>'
                )
            output.append(text_element(f"{panel_id}-x-tick-{index}", x, plot["y"] + plot["height"] + font_size * 1.35, f"{tick:g}", font_size))

        for index, tick_raw in enumerate(panel["y_ticks"]):
            tick = number(tick_raw, f"{panel_id}.y_ticks")
            y = plot["y"] + plot["height"] - (tick - y_min) / (y_max - y_min) * plot["height"]
            if tick != y_min and tick != y_max:
                output.append(
                    f'<line id="{esc(panel_id)}-y-grid-{index}" class="grid" x1="{fmt(plot["x"])}" y1="{fmt(y)}" '
                    f'x2="{fmt(plot["x"] + plot["width"])}" y2="{fmt(y)}" stroke-width="{fmt(grid_stroke)}"/>'
                )
            output.append(text_element(f"{panel_id}-y-tick-{index}", plot["x"] - font_size * 0.65, y + font_size * 0.34, str(tick_raw), font_size, anchor="end"))

        output.append(
            f'<rect id="{esc(panel_id)}-axes" class="axis" x="{fmt(plot["x"])}" y="{fmt(plot["y"])}" '
            f'width="{fmt(plot["width"])}" height="{fmt(plot["height"])}" stroke-width="{fmt(axis_stroke)}"/>'
        )
        output.append(text_element(
            f"{panel_id}-x-label", plot["x"] + plot["width"] / 2,
            plot["y"] + plot["height"] + font_size * 2.55, panel["x_label"], font_size,
        ))
        y_center = plot["y"] + plot["height"] / 2
        output.append(text_element(
            f"{panel_id}-y-label", plot["x"] - font_size * 2.35, y_center,
            panel["y_label"], font_size, transform=f"rotate(-90 {fmt(plot['x'] - font_size * 2.35)} {fmt(y_center)})",
        ))

        for series_index, series in enumerate(panel["series"]):
            points = point_series(rows, x_key, str(series["column"]), x_min, x_max, y_min, y_max, plot)
            output.append(
                f'<polyline id="{esc(series["id"])}" class="curve" points="{points}" '
                f'stroke="{esc(series["color"])}" stroke-width="{fmt(curve_stroke)}"/>'
            )
            # Keep a full 8.5 pt English label inside the plot even on a
            # two-column 180 mm page.  The offset is physical because
            # ``font_size`` is already expressed in canvas units.
            legend_x = plot["x"] + plot["width"] - font_size * 9.3
            legend_y = plot["y"] + plot["height"] - font_size * (2.5 - series_index * 1.35)
            output.append(
                f'<line id="{esc(series["id"])}-legend-line" x1="{fmt(legend_x)}" y1="{fmt(legend_y)}" '
                f'x2="{fmt(legend_x + font_size * 1.5)}" y2="{fmt(legend_y)}" stroke="{esc(series["color"])}" '
                f'stroke-width="{fmt(curve_stroke)}"/>'
            )
            output.append(text_element(
                f"{series['id']}-legend-label", legend_x + font_size * 1.85,
                legend_y + font_size * 0.34, str(series["label"]), font_size, anchor="start",
            ))

        output.append(text_element(
            f"{panel_id}-caption", plot["x"] + plot["width"] / 2,
            number(panel["caption_y"], f"{panel_id}.caption_y"), str(panel["caption"]), font_size,
        ))
        output.append('</g>')

    output.append('</svg>')
    return "\n".join(output) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("recipe", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    recipe_path = args.recipe.resolve()
    output = args.output.resolve()
    if output.exists() and not args.force:
        fail(f"Output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render(load_json(recipe_path), recipe_path), encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
