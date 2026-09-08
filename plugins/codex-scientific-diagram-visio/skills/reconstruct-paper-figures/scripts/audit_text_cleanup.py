from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import statistics
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from PIL import Image, ImageFilter


SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
DEFAULT_MAX_AREA_FRACTION = 0.25
DEFAULT_RESIDUAL_PIXEL_FRACTION = 0.05
DEFAULT_HALO_PAIR_FRACTION = 0.10
NUMBER_UNIT_RE = re.compile(
    r"^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*(pt|px)?\s*$",
    re.IGNORECASE,
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def pixel_sha256(image: Image.Image, mode: str = "RGBA") -> str:
    normalized = image.convert(mode)
    digest = hashlib.sha256()
    digest.update(("%s:%dx%d:" % (mode, normalized.width, normalized.height)).encode("ascii"))
    digest.update(normalized.tobytes())
    return digest.hexdigest()


def flat_data(image: Image.Image):
    modern = getattr(image, "get_flattened_data", None)
    return modern() if modern is not None else image.getdata()


def resolve_inside_workspace(raw: str, base: Path, *, must_exist: bool = True) -> Path:
    workspace = Path.cwd().resolve()
    requested = Path(raw)
    path = (requested if requested.is_absolute() else base / requested).resolve()
    if path != workspace and workspace not in path.parents:
        raise ValueError("Path must stay inside workspace: %s" % path)
    if must_exist and not path.is_file():
        raise FileNotFoundError(path)
    return path


def add_issue(issues: List[Dict[str, Any]], code: str, **details: Any) -> None:
    issues.append({"code": code, **details})


def require_distinct_paths(named_paths: Sequence[Tuple[str, Optional[Path]]]) -> None:
    seen: Dict[Path, str] = {}
    for name, path in named_paths:
        if path is None:
            continue
        resolved = path.resolve()
        previous = seen.get(resolved)
        if previous is not None:
            raise ValueError("Audit paths must be distinct: %s and %s both resolve to %s" % (
                previous,
                name,
                resolved,
            ))
        seen[resolved] = name


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_style(raw: str) -> Dict[str, str]:
    parsed: Dict[str, str] = {}
    for token in raw.split(";"):
        if ":" not in token:
            continue
        key, value = token.split(":", 1)
        parsed[key.strip().lower()] = value.strip()
    return parsed


def normalized_font_family(value: str) -> str:
    primary = value.split(",", 1)[0].strip().strip("'\"")
    return re.sub(r"\s+", " ", primary).casefold()


def font_size_pt(raw: str, user_unit_to_pt: Optional[float] = None) -> Optional[float]:
    match = NUMBER_UNIT_RE.fullmatch(str(raw))
    if not match:
        return None
    value = float(match.group(1))
    unit = (match.group(2) or "").lower()
    if user_unit_to_pt is not None and unit in {"", "px"}:
        return value * user_unit_to_pt
    return value if unit == "pt" else value * 72.0 / 96.0


def visible_style(style: Dict[str, str]) -> bool:
    if style.get("__ancestor_hidden__") == "true":
        return False
    if style.get("display", "").strip().lower() == "none":
        return False
    if style.get("visibility", "").strip().lower() in {"hidden", "collapse"}:
        return False
    for key in ("opacity", "fill-opacity"):
        if key in style:
            try:
                if float(style[key]) <= 0:
                    return False
            except ValueError:
                return False
    return True


def merged_style(element: ET.Element, inherited: Dict[str, str]) -> Dict[str, str]:
    merged = dict(inherited)
    for key in ("font-family", "font-size", "display", "visibility", "opacity", "fill-opacity"):
        if key in element.attrib:
            merged[key] = element.attrib[key]
    merged.update(parse_style(element.attrib.get("style", "")))
    return merged


def iter_svg_with_style(
    element: ET.Element, inherited: Optional[Dict[str, str]] = None
) -> Iterable[Tuple[ET.Element, Dict[str, str]]]:
    inherited_style = inherited or {}
    current = merged_style(element, inherited_style)
    if inherited_style.get("__effective_visible__") == "false" or inherited_style.get(
        "__nonrender_container__"
    ) == "true":
        current["__ancestor_hidden__"] = "true"
    if local_name(element.tag) in {"defs", "symbol", "clipPath", "mask", "pattern", "marker"}:
        current["__nonrender_container__"] = "true"
    current["__effective_visible__"] = "true" if visible_style(current) else "false"
    yield element, current
    for child in list(element):
        yield from iter_svg_with_style(child, current)


def external_reference_issues(root: ET.Element) -> List[dict]:
    issues: List[dict] = []
    forbidden_elements = {"script", "style", "foreignObject", "feImage"}
    for element in root.iter():
        name = local_name(element.tag)
        if name in forbidden_elements:
            issues.append({"code": "replacement_svg_forbidden_element", "element": name})
        for raw_key, raw_value in element.attrib.items():
            key = local_name(raw_key).lower()
            value = str(raw_value).strip()
            if key.startswith("on"):
                issues.append(
                    {"code": "replacement_svg_event_handler", "element": name, "attribute": key}
                )
            if key in {"href", "src"} and not (
                value.startswith("#") or value.startswith("data:image/")
            ):
                issues.append(
                    {
                        "code": "replacement_svg_external_reference",
                        "element": name,
                        "attribute": key,
                        "value": value,
                    }
                )
            for match in re.finditer(r"url\(([^)]+)\)", value, re.IGNORECASE):
                target = match.group(1).strip().strip("'\"")
                if not target.startswith("#"):
                    issues.append(
                        {
                            "code": "replacement_svg_external_reference",
                            "element": name,
                            "attribute": key,
                            "value": target,
                        }
                    )
    return issues


def audit_replacement_svg(
    path: Path,
    expected_font_family: str,
    expected_font_size_pt: float,
    required_text_ids: Sequence[str],
) -> dict:
    issues: List[Dict[str, Any]] = []
    try:
        root = ET.parse(str(path)).getroot()
    except ET.ParseError as exc:
        return {
            "provided": True,
            "pass": False,
            "file": str(path),
            "sha256": sha256_file(path),
            "live_text_count": 0,
            "texts": [],
            "issues": [{"code": "replacement_svg_parse_error", "detail": str(exc)}],
        }
    if local_name(root.tag) != "svg":
        add_issue(issues, "replacement_svg_root_invalid", actual=local_name(root.tag))
    user_unit_to_pt: Optional[float] = None
    if root.attrib.get("data-physical-font-scaling") == "viewBox-to-mm":
        width_match = re.fullmatch(r"\s*([0-9]+(?:\.[0-9]+)?)mm\s*", root.attrib.get("width", ""))
        view_box = root.attrib.get("viewBox", "").replace(",", " ").split()
        if width_match and len(view_box) == 4:
            try:
                view_box_width = float(view_box[2])
                if view_box_width > 0:
                    user_unit_to_pt = float(width_match.group(1)) * 72.0 / 25.4 / view_box_width
            except ValueError:
                user_unit_to_pt = None
        if user_unit_to_pt is None:
            add_issue(issues, "replacement_svg_physical_font_scale_invalid")
    issues.extend(external_reference_issues(root))
    texts: List[dict] = []
    ids: List[str] = []
    all_ids = [
        element.attrib["id"]
        for element in root.iter()
        if str(element.attrib.get("id", "")).strip()
    ]
    duplicate_document_ids = sorted({value for value in all_ids if all_ids.count(value) > 1})
    if duplicate_document_ids:
        add_issue(issues, "replacement_svg_duplicate_ids", ids=duplicate_document_ids)
    for element, style in iter_svg_with_style(root):
        if local_name(element.tag) != "text":
            continue
        text_id = element.attrib.get("id")
        content = "".join(element.itertext()).strip()
        actual_family = style.get("font-family")
        actual_size_raw = style.get("font-size")
        actual_size_pt = (
            font_size_pt(actual_size_raw, user_unit_to_pt=user_unit_to_pt)
            if actual_size_raw is not None else None
        )
        visible = visible_style(style)
        item_issues: List[str] = []
        if not text_id:
            item_issues.append("live_text_id_missing")
        else:
            ids.append(text_id)
        if not content:
            item_issues.append("live_text_empty")
        if not visible:
            item_issues.append("live_text_hidden")
        if actual_family is None or normalized_font_family(actual_family) != normalized_font_family(
            expected_font_family
        ):
            item_issues.append("live_text_font_family_mismatch")
        if actual_size_pt is None or not math.isclose(
            actual_size_pt, expected_font_size_pt, abs_tol=0.05
        ):
            item_issues.append("live_text_font_size_mismatch")
        if item_issues:
            add_issue(issues, "replacement_live_text_invalid", id=text_id, findings=item_issues)
        texts.append(
            {
                "id": text_id,
                "content": content,
                "visible": visible,
                "font_family": actual_family,
                "font_size_raw": actual_size_raw,
                "font_size_pt": actual_size_pt,
                "issues": item_issues,
            }
        )
    if not texts:
        add_issue(issues, "replacement_live_text_missing")
    duplicate_ids = sorted({value for value in ids if ids.count(value) > 1})
    if duplicate_ids:
        add_issue(issues, "replacement_live_text_duplicate_ids", ids=duplicate_ids)
    missing_ids = sorted(set(required_text_ids) - set(ids))
    if missing_ids:
        add_issue(issues, "replacement_required_text_ids_missing", ids=missing_ids)
    return {
        "provided": True,
        "pass": not issues,
        "file": str(path),
        "sha256": sha256_file(path),
        "live_text_count": len(texts),
        "texts": texts,
        "issues": issues,
    }


def canonical_mask(image: Image.Image) -> Tuple[Optional[Image.Image], List[dict]]:
    issues: List[dict] = []
    rgba = image.convert("RGBA")
    values: List[int] = []
    invalid_count = 0
    for red, green, blue, alpha in flat_data(rgba):
        if alpha != 255 or red != green or red != blue or red not in {0, 255}:
            invalid_count += 1
            values.append(0)
        else:
            values.append(red)
    if invalid_count:
        add_issue(issues, "mask_not_binary", invalid_pixel_count=invalid_count)
        return None, issues
    result = Image.new("L", rgba.size)
    result.putdata(values)
    return result, issues


def validate_protected_regions(
    regions: Sequence[dict], size: Tuple[int, int], issues: List[Dict[str, Any]]
) -> List[dict]:
    width, height = size
    validated: List[dict] = []
    seen = set()
    for index, region in enumerate(regions):
        if not isinstance(region, dict):
            add_issue(issues, "protected_region_invalid", index=index)
            continue
        region_id = str(region.get("id", "")).strip()
        bbox = region.get("bbox_px") or region.get("rect_px")
        if not region_id or region_id in seen:
            add_issue(issues, "protected_region_id_invalid", index=index, id=region_id)
            continue
        seen.add(region_id)
        if not isinstance(bbox, list) or len(bbox) != 4:
            add_issue(issues, "protected_region_bbox_invalid", id=region_id)
            continue
        try:
            x, y, box_width, box_height = [int(value) for value in bbox]
        except (TypeError, ValueError):
            add_issue(issues, "protected_region_bbox_invalid", id=region_id)
            continue
        if (
            x < 0
            or y < 0
            or box_width <= 0
            or box_height <= 0
            or x + box_width > width
            or y + box_height > height
        ):
            add_issue(issues, "protected_region_out_of_bounds", id=region_id, bbox_px=bbox)
            continue
        validated.append({"id": region_id, "bbox_px": [x, y, box_width, box_height]})
    return validated


def count_nonzero(image: Image.Image) -> int:
    return sum(1 for value in flat_data(image) if value)


def mask_intersection_count(mask: Image.Image, bbox: Sequence[int]) -> int:
    x, y, width, height = bbox
    return count_nonzero(mask.crop((x, y, x + width, y + height)))


def difference_mask(source: Image.Image, cleaned: Image.Image) -> Image.Image:
    source_rgba = source.convert("RGBA")
    cleaned_rgba = cleaned.convert("RGBA")
    output = Image.new("L", source_rgba.size)
    output.putdata([
        255 if source_pixel != cleaned_pixel else 0
        for source_pixel, cleaned_pixel in zip(flat_data(source_rgba), flat_data(cleaned_rgba))
    ])
    return output


def logical_outside(mask: Image.Image, changed: Image.Image) -> Image.Image:
    output = Image.new("L", mask.size)
    output.putdata([
        255 if changed_value and not mask_value else 0
        for mask_value, changed_value in zip(flat_data(mask), flat_data(changed))
    ])
    return output


def gray_values(image: Image.Image, selector: Image.Image) -> List[int]:
    gray = image.convert("L")
    return [value for value, selected in zip(flat_data(gray), flat_data(selector)) if selected]


def cleanup_heuristics(
    cleaned: Image.Image,
    mask: Image.Image,
    residual_fraction_limit: float,
    halo_fraction_limit: float,
) -> dict:
    issues: List[Dict[str, Any]] = []
    dilated = mask.filter(ImageFilter.MaxFilter(3))
    eroded = mask.filter(ImageFilter.MinFilter(3))
    outer_ring = Image.new("L", mask.size)
    outer_ring.putdata([
        255 if dilated_value and not mask_value else 0
        for dilated_value, mask_value in zip(flat_data(dilated), flat_data(mask))
    ])
    inner_boundary = Image.new("L", mask.size)
    inner_boundary.putdata([
        255 if mask_value and not eroded_value else 0
        for mask_value, eroded_value in zip(flat_data(mask), flat_data(eroded))
    ])
    inner_values = gray_values(cleaned, mask)
    outer_values = gray_values(cleaned, outer_ring)
    if not inner_values:
        add_issue(issues, "mask_has_no_selected_pixels")
        return {
            "pass": False,
            "issues": issues,
            "background_median": None,
            "background_mad": None,
            "residual_threshold": None,
            "residual_pixel_fraction": None,
            "halo_pair_fraction": None,
        }
    if not outer_values:
        add_issue(issues, "mask_has_no_outer_review_ring")
        return {
            "pass": False,
            "issues": issues,
            "background_median": None,
            "background_mad": None,
            "residual_threshold": None,
            "residual_pixel_fraction": None,
            "halo_pair_fraction": None,
        }
    background_median = float(statistics.median(outer_values))
    background_mad = float(
        statistics.median(abs(value - background_median) for value in outer_values)
    )
    threshold = max(12.0, 4.0 * background_mad + 4.0)
    residual_count = sum(abs(value - background_median) > threshold for value in inner_values)
    residual_fraction = residual_count / float(len(inner_values))
    if residual_fraction > residual_fraction_limit:
        add_issue(
            issues,
            "possible_residual_glyph",
            pixel_fraction=residual_fraction,
            limit=residual_fraction_limit,
        )

    gray = cleaned.convert("L")
    gray_pixels = gray.load()
    mask_pixels = mask.load()
    boundary_pixels = inner_boundary.load()
    width, height = mask.size
    halo_pairs: List[int] = []
    for y in range(height):
        for x in range(width):
            if not boundary_pixels[x, y]:
                continue
            for offset_x, offset_y in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                neighbor_x = x + offset_x
                neighbor_y = y + offset_y
                if not (0 <= neighbor_x < width and 0 <= neighbor_y < height):
                    continue
                if mask_pixels[neighbor_x, neighbor_y]:
                    continue
                halo_pairs.append(abs(gray_pixels[x, y] - gray_pixels[neighbor_x, neighbor_y]))
    halo_fraction = (
        sum(value > threshold for value in halo_pairs) / float(len(halo_pairs))
        if halo_pairs
        else 0.0
    )
    if halo_fraction > halo_fraction_limit:
        add_issue(
            issues,
            "possible_cleanup_halo",
            pair_fraction=halo_fraction,
            limit=halo_fraction_limit,
        )
    return {
        "pass": not issues,
        "issues": issues,
        "background_median": background_median,
        "background_mad": background_mad,
        "residual_threshold": threshold,
        "residual_pixel_fraction": residual_fraction,
        "residual_pixel_count": residual_count,
        "halo_pair_fraction": halo_fraction,
        "halo_pair_count": len(halo_pairs),
    }


def audit_text_cleanup(
    source_path: Path,
    cleaned_path: Path,
    mask_path: Path,
    *,
    replacement_svg_path: Optional[Path] = None,
    protected_regions: Sequence[dict] = (),
    max_mask_area_fraction: float = DEFAULT_MAX_AREA_FRACTION,
    max_changed_area_fraction: float = DEFAULT_MAX_AREA_FRACTION,
    residual_pixel_fraction_limit: float = DEFAULT_RESIDUAL_PIXEL_FRACTION,
    halo_pair_fraction_limit: float = DEFAULT_HALO_PAIR_FRACTION,
    expected_font_family: str = "Times New Roman",
    expected_font_size_pt: float = 8.5,
    required_text_ids: Sequence[str] = (),
) -> dict:
    base = Path.cwd()
    source_path = resolve_inside_workspace(str(source_path), base)
    cleaned_path = resolve_inside_workspace(str(cleaned_path), base)
    mask_path = resolve_inside_workspace(str(mask_path), base)
    if replacement_svg_path is not None:
        replacement_svg_path = resolve_inside_workspace(str(replacement_svg_path), base)
    require_distinct_paths(
        (
            ("source", source_path),
            ("cleaned", cleaned_path),
            ("mask", mask_path),
            ("replacement_svg", replacement_svg_path),
        )
    )
    issues: List[Dict[str, Any]] = []
    for name, value in (
        ("max_mask_area_fraction", max_mask_area_fraction),
        ("max_changed_area_fraction", max_changed_area_fraction),
        ("residual_pixel_fraction_limit", residual_pixel_fraction_limit),
        ("halo_pair_fraction_limit", halo_pair_fraction_limit),
    ):
        if not 0 <= value <= 1:
            raise ValueError("%s must be between 0 and 1" % name)
    if expected_font_size_pt <= 0:
        raise ValueError("expected_font_size_pt must be positive")

    with Image.open(str(source_path)) as source_image, Image.open(
        str(cleaned_path)
    ) as cleaned_image, Image.open(str(mask_path)) as raw_mask:
        source = source_image.copy()
        cleaned = cleaned_image.copy()
        mask_source = raw_mask.copy()
    if source.size != cleaned.size:
        add_issue(
            issues,
            "source_cleaned_size_mismatch",
            source_size=list(source.size),
            cleaned_size=list(cleaned.size),
        )
    if source.size != mask_source.size:
        add_issue(
            issues,
            "mask_size_mismatch",
            source_size=list(source.size),
            mask_size=list(mask_source.size),
        )
    mask, mask_issues = canonical_mask(mask_source)
    issues.extend(mask_issues)

    validated_regions = validate_protected_regions(protected_regions, source.size, issues)
    total_pixels = source.width * source.height
    mask_pixels = count_nonzero(mask) if mask is not None and mask.size == source.size else 0
    mask_fraction = mask_pixels / float(total_pixels) if total_pixels else 0.0
    if mask is not None and mask_pixels == 0:
        add_issue(issues, "mask_empty")
    if mask_fraction > max_mask_area_fraction:
        add_issue(
            issues,
            "mask_area_fraction_exceeded",
            actual=mask_fraction,
            limit=max_mask_area_fraction,
        )

    changed: Optional[Image.Image] = None
    changed_pixels = 0
    outside_mask_changed_pixels = 0
    protected_results: List[dict] = []
    heuristics: dict = {
        "pass": False,
        "issues": [{"code": "cleanup_heuristics_not_run"}],
    }
    if source.size == cleaned.size and mask is not None and mask.size == source.size:
        changed = difference_mask(source, cleaned)
        changed_pixels = count_nonzero(changed)
        outside = logical_outside(mask, changed)
        outside_mask_changed_pixels = count_nonzero(outside)
        if outside_mask_changed_pixels:
            add_issue(
                issues,
                "outside_mask_pixels_changed",
                pixel_count=outside_mask_changed_pixels,
            )
        changed_fraction = changed_pixels / float(total_pixels)
        if changed_fraction > max_changed_area_fraction:
            add_issue(
                issues,
                "changed_area_fraction_exceeded",
                actual=changed_fraction,
                limit=max_changed_area_fraction,
            )
        for region in validated_regions:
            mask_overlap = mask_intersection_count(mask, region["bbox_px"])
            changed_overlap = mask_intersection_count(changed, region["bbox_px"])
            protected_results.append(
                {
                    "id": region["id"],
                    "bbox_px": region["bbox_px"],
                    "mask_overlap_pixels": mask_overlap,
                    "changed_overlap_pixels": changed_overlap,
                    "pass": mask_overlap == 0 and changed_overlap == 0,
                }
            )
            if mask_overlap:
                add_issue(
                    issues,
                    "mask_intersects_protected_region",
                    id=region["id"],
                    pixel_count=mask_overlap,
                )
            if changed_overlap:
                add_issue(
                    issues,
                    "protected_region_pixels_changed",
                    id=region["id"],
                    pixel_count=changed_overlap,
                )
        heuristics = cleanup_heuristics(
            cleaned,
            mask,
            residual_pixel_fraction_limit,
            halo_pair_fraction_limit,
        )
        issues.extend(heuristics["issues"])
    else:
        changed_fraction = 0.0

    replacement = (
        audit_replacement_svg(
            replacement_svg_path,
            expected_font_family,
            expected_font_size_pt,
            required_text_ids,
        )
        if replacement_svg_path is not None
        else {
            "provided": False,
            "pass": None,
            "live_text_count": 0,
            "texts": [],
            "issues": [],
            "note": "No replacement SVG was supplied; live text was not audited.",
        }
    )
    if replacement_svg_path is not None:
        issues.extend(replacement["issues"])
    elif required_text_ids:
        add_issue(
            issues,
            "replacement_svg_required_for_declared_text_ids",
            ids=sorted(set(str(value) for value in required_text_ids)),
        )

    audit_pass = not issues
    return {
        "schema_version": "text-cleanup-audit-v1",
        "pass": audit_pass,
        "publication_ready": False,
        "manual_approval_required": True,
        "source": {
            "file": str(source_path),
            "sha256": sha256_file(source_path),
            "pixel_sha256_rgba": pixel_sha256(source),
            "mode": source.mode,
            "size_px": list(source.size),
        },
        "cleaned": {
            "file": str(cleaned_path),
            "sha256": sha256_file(cleaned_path),
            "pixel_sha256_rgba": pixel_sha256(cleaned),
            "mode": cleaned.mode,
            "size_px": list(cleaned.size),
        },
        "mask": {
            "file": str(mask_path),
            "sha256": sha256_file(mask_path),
            "source_mode": mask_source.mode,
            "binary": mask is not None,
            "selected_pixels": mask_pixels,
            "area_fraction": mask_fraction,
            "max_area_fraction": max_mask_area_fraction,
        },
        "pixel_changes": {
            "changed_pixels": changed_pixels,
            "changed_area_fraction": changed_pixels / float(total_pixels) if total_pixels else 0.0,
            "max_changed_area_fraction": max_changed_area_fraction,
            "outside_mask_changed_pixels": outside_mask_changed_pixels,
            "outside_mask_zero_change": outside_mask_changed_pixels == 0
            and changed is not None,
        },
        "protected_regions": protected_results,
        "heuristics": heuristics,
        "replacement_svg": replacement,
        "issues": issues,
        "note": (
            "A passing machine audit proves only the declared pixel and SVG invariants. "
            "It never grants publication readiness; an editor must inspect the cleaned area "
            "at 200%-400% and explicitly approve it."
        ),
    }


def load_config(path: Optional[Path]) -> dict:
    if path is None:
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Audit config must be a JSON object")
    allowed = {
        "protected_regions",
        "max_mask_area_fraction",
        "max_changed_area_fraction",
        "residual_pixel_fraction_limit",
        "halo_pair_fraction_limit",
        "expected_font_family",
        "expected_font_size_pt",
        "required_text_ids",
    }
    unexpected = sorted(set(payload) - allowed)
    if unexpected:
        raise ValueError("Unsupported audit config fields: " + ", ".join(unexpected))
    if not isinstance(payload.get("protected_regions", []), list):
        raise ValueError("protected_regions must be a list")
    if not isinstance(payload.get("required_text_ids", []), list):
        raise ValueError("required_text_ids must be a list")
    return payload


def atomic_write_json(path: Path, payload: dict, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError("Output exists; choose a new path or pass --force: %s" % path)
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
    parser = argparse.ArgumentParser(
        description="Audit a non-generative text cleanup without modifying its inputs."
    )
    parser.add_argument("source", type=lambda raw: resolve_inside_workspace(raw, Path.cwd()))
    parser.add_argument("cleaned", type=lambda raw: resolve_inside_workspace(raw, Path.cwd()))
    parser.add_argument("mask", type=lambda raw: resolve_inside_workspace(raw, Path.cwd()))
    parser.add_argument(
        "--replacement-svg", type=lambda raw: resolve_inside_workspace(raw, Path.cwd())
    )
    parser.add_argument("--config", type=lambda raw: resolve_inside_workspace(raw, Path.cwd()))
    parser.add_argument(
        "--json-out",
        type=lambda raw: resolve_inside_workspace(raw, Path.cwd(), must_exist=False),
    )
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--require-pass", action="store_true")
    args = parser.parse_args()
    require_distinct_paths(
        (
            ("source", args.source),
            ("cleaned", args.cleaned),
            ("mask", args.mask),
            ("replacement_svg", args.replacement_svg),
            ("config", args.config),
            ("json_out", args.json_out),
        )
    )
    config = load_config(args.config)
    result = audit_text_cleanup(
        args.source,
        args.cleaned,
        args.mask,
        replacement_svg_path=args.replacement_svg,
        **config,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.json_out:
        atomic_write_json(args.json_out, result, args.force)
    if args.require_pass and not result["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
