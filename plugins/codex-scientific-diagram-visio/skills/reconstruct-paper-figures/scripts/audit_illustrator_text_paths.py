from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path


def flatten_text_paths(elements: list[dict], parent_id: str | None = None) -> list[dict]:
    flattened = []
    for element in elements:
        if element.get("type") == "text_path":
            flattened.append({"element": element, "parent_id": parent_id})
        if element.get("type") == "group":
            flattened.extend(flatten_text_paths(element.get("children", []), element.get("id")))
    return flattened


def element_text(element: dict) -> str:
    if "text" in element:
        return str(element["text"])
    return "".join(str(run.get("text", "")) for run in element.get("runs", []))


def expected_postscript_font(family: str, weight: str, style: str) -> str | None:
    if family.casefold() != "times new roman":
        return None
    bold = weight.casefold() == "bold" or (weight.isdigit() and int(weight) >= 600)
    italic = style.casefold() in {"italic", "oblique"}
    if bold and italic:
        return "TimesNewRomanPS-BoldItalicMT"
    if bold:
        return "TimesNewRomanPS-BoldMT"
    if italic:
        return "TimesNewRomanPS-ItalicMT"
    return "TimesNewRomanPSMT"


def rgb_from_hex(value: str) -> tuple[int, int, int] | None:
    text = str(value)
    if len(text) != 7 or not text.startswith("#"):
        return None
    try:
        return tuple(int(text[index : index + 2], 16) for index in (1, 3, 5))
    except ValueError:
        return None


def rgb_tuple(color: dict | None) -> tuple[float, float, float] | None:
    if not isinstance(color, dict) or color.get("type") != "RGB":
        return None
    try:
        return float(color["red"]), float(color["green"]), float(color["blue"])
    except (KeyError, TypeError, ValueError):
        return None


def rgb_matches(color: dict | None, expected: tuple[int, int, int] | None) -> bool:
    actual = rgb_tuple(color)
    return bool(
        actual
        and expected
        and all(abs(actual[index] - expected[index]) <= 0.5 for index in range(3))
    )


def nonempty_bounds(value: object) -> bool:
    if not isinstance(value, list) or len(value) != 4:
        return False
    try:
        left, top, right, bottom = (float(item) for item in value)
    except (TypeError, ValueError):
        return False
    return right > left and top > bottom


def contains_contiguous_fragment_phrase(
    frames: list[dict],
    phrase: str,
    size_pt: float,
    expected_font: str | None,
    expected_fill: tuple[int, int, int] | None,
) -> bool:
    groups: dict[tuple, list[str]] = {}
    for frame in frames:
        content = str(frame.get("contents", ""))
        if (
            frame.get("kind") != "point"
            or frame.get("name")
            or frame.get("hidden")
            or frame.get("locked")
            or len(content) != 1
            or abs(float(frame.get("size_pt", -1000)) - size_pt) > 0.2
            or (expected_font and frame.get("font_postscript_name") != expected_font)
            or not rgb_matches(frame.get("fill"), expected_fill)
        ):
            continue
        parent = frame.get("parent") or {}
        key = (
            parent.get("typename", "<legacy-parent>"),
            parent.get("name", "<legacy-parent>"),
            frame.get("font_postscript_name"),
            round(float(frame.get("size_pt", 0)), 2),
            rgb_tuple(frame.get("fill")),
        )
        groups.setdefault(key, []).append(content)
    return any(
        phrase in (imported := "".join(characters)) or phrase[::-1] in imported
        for characters in groups.values()
    )


def audit_payload(recipe: dict, illustrator_audit: dict) -> dict:
    defaults = recipe.get("defaults", {})
    frames = illustrator_audit.get("text_frames", [])
    issues = []
    text_path_results = []
    for record in flatten_text_paths(recipe.get("elements", [])):
        element = record["element"]
        element_id = str(element["id"])
        phrase = element_text(element)
        family = str(element.get("font_family", defaults.get("font_family", "Times New Roman")))
        weight = str(element.get("font_weight", "normal"))
        style = str(element.get("font_style", "normal"))
        size_pt = float(element.get("font_size_pt", defaults.get("font_size_pt", 8.5)))
        expected_font = expected_postscript_font(family, weight, style)
        expected_fill = rgb_from_hex(str(element.get("fill", defaults.get("text_fill", "#000000"))))
        named = [frame for frame in frames if frame.get("name") == element_id]
        item_issues = []
        if len(named) != 1:
            item_issues.append(f"expected_one_named_text_frame_got_{len(named)}")
        else:
            frame = named[0]
            if frame.get("kind") != "path":
                item_issues.append("named_frame_is_not_path_text")
            if frame.get("contents") != phrase:
                item_issues.append("phrase_content_mismatch")
            if abs(float(frame.get("size_pt", -1000)) - size_pt) > 0.05:
                item_issues.append("font_size_mismatch")
            if expected_font and frame.get("font_postscript_name") != expected_font:
                item_issues.append("font_postscript_name_mismatch")
            if not rgb_matches(frame.get("fill"), expected_fill):
                item_issues.append("fill_color_mismatch")
            if frame.get("hidden"):
                item_issues.append("named_frame_is_hidden")
            if frame.get("locked"):
                item_issues.append("named_frame_is_locked")
            bounds = frame.get("bounds_pt")
            if not nonempty_bounds(bounds):
                item_issues.append("missing_or_empty_bounds")
            parent = frame.get("parent") or {}
            accepted_parent_names = {
                str(record["parent_id"] or ""),
                str(record["parent_id"] or "").replace("_", " "),
            }
            if (
                record["parent_id"]
                and (
                    parent.get("typename") != "GroupItem"
                    or parent.get("name") not in accepted_parent_names
                )
            ):
                item_issues.append("parent_group_mismatch")
            path_data = frame.get("text_path")
            if not isinstance(path_data, dict):
                item_issues.append("text_path_geometry_missing")
            else:
                if path_data.get("closed"):
                    item_issues.append("text_path_must_be_open")
                if int(path_data.get("point_count", 0)) < 2:
                    item_issues.append("text_path_has_too_few_points")
                if not nonempty_bounds(path_data.get("bounds_pt")):
                    item_issues.append("text_path_bounds_missing_or_empty")
        fragmented = contains_contiguous_fragment_phrase(
            frames, phrase, size_pt, expected_font, expected_fill
        )
        if fragmented:
            item_issues.append("split_point_text_phrase_still_present")
        if item_issues:
            issues.append({"id": element_id, "issues": item_issues})
        text_path_results.append(
            {
                "id": element_id,
                "phrase": phrase,
                "expected_parent_id": record["parent_id"],
                "named_frame_count": len(named),
                "fragmented_point_text_detected": fragmented,
                "issues": item_issues,
            }
        )
    return {
        "pass": not issues,
        "source_audit": illustrator_audit.get("source_document"),
        "expected_text_path_count": len(text_path_results),
        "text_path_results": text_path_results,
        "issues": issues,
        "note": (
            "This audit checks Illustrator structure recorded by audit_active_document.jsx. "
            "It does not replace visual inspection of path direction, centering, or glyph rendering."
        ),
    }


def write_json_output(path: Path, payload: dict, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"Output exists; choose a new name or pass --force: {path}")
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
    parser = argparse.ArgumentParser(
        description="Audit phrase-level Illustrator path text using recipe and Illustrator audit JSON."
    )
    parser.add_argument("recipe", type=Path)
    parser.add_argument("illustrator_audit", type=Path)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    recipe = json.loads(args.recipe.read_text(encoding="utf-8"))
    illustrator_audit = json.loads(args.illustrator_audit.read_text(encoding="utf-8"))
    result = audit_payload(recipe, illustrator_audit)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.json_out:
        write_json_output(args.json_out, result, args.force)
    if not result["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
