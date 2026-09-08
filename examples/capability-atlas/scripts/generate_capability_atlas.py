#!/usr/bin/env python3
"""Generate and audit eight editable capability-atlas SVG sheets."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image


MODULE = Path(__file__).resolve().parents[1]
ROOT = MODULE.parents[1]
SRC = MODULE / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from atlas_catalog import CATEGORIES, WORKLOAD_PROFILES, all_cards, consumption_for  # noqa: E402
from atlas_elements import build_card, rect, text  # noqa: E402


WIDTH, HEIGHT = 1600, 900
SVG_NS = "{http://www.w3.org/2000/svg}"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_text_lf(path, content):
    """Write reproducible text bytes on Windows and Unix."""

    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)


def make_recipe(category):
    accent = category["accent"]
    elements = [
        rect("atlas", "header.band", 0, 0, WIDTH, 104, accent, "none", 0),
        text("atlas", "title", category["title"], 56, 50, 22, "#FFFFFF", "start", "bold"),
        text("atlas", "title.zh", category["title_zh"], 56, 82, 11, "#FFFFFF"),
        text("atlas", "badge", "8 EDITABLE FIGURE FAMILIES", 1538, 65, 8, "#FFFFFF", "end", "bold"),
    ]
    card_w, card_h = 362, 354
    for index, (title_value, subtitle, kind) in enumerate(category["cards"]):
        col, row = index % 4, index // 4
        x, y = 37 + col * 389, 127 + row * 379
        prefix = f"card.{index+1:02d}.{kind}"
        elements.append(
            build_card(
                prefix, title_value, subtitle, kind, consumption_for(kind),
                x, y, card_w, card_h, accent,
            )
        )
    elements.append(text("atlas", "footer", "Atlas build: local deterministic Python · 0 model/API calls · live text · zero raster", 800, 884, 7.5, "#667384", "middle"))
    return {
        "title": f"Capability Atlas — {category['title']}",
        "source_image": "../source/blank.png",
        "figure_class": "capability-atlas",
        "recovery_level": "R1",
        "canvas": {"width_px": WIDTH, "height_px": HEIGHT, "print_width_mm": 320, "background_fill": "#F4F6F8"},
        "defaults": {"font_family": "Arial", "font_size_pt": 8.5, "text_fill": "#233042", "stroke_width_mm": 0.22},
        "contract": {"required_live_text": True, "required_font_family": "Arial", "require_zero_rasters": True, "manual_review_required": True},
        "elements": elements,
        "metadata": {"category_id": category["id"], "demonstration": True, "source_data_claim": False},
    }


def audit_svg(svg_path, category):
    root = ET.parse(svg_path).getroot()
    ids = [node.attrib.get("id", "") for node in root.iter()]
    texts = list(root.iter(f"{SVG_NS}text"))
    images = list(root.iter(f"{SVG_NS}image"))
    cards = [
        node for node in root.iter()
        if node.attrib.get("id", "").startswith("card.")
        and node.attrib.get("id", "").count(".") == 2
    ]
    missing = [kind for _, _, kind in category["cards"] if not any(f".{kind}" in value for value in ids)]
    if len(cards) != 8 or images or missing:
        raise RuntimeError(f"Audit failed for {svg_path.name}: cards={len(cards)}, rasters={len(images)}, missing={missing}")
    card_counts = {
        card.attrib["id"]: sum(1 for _ in card.iter()) - 1
        for card in cards
    }
    if min(card_counts.values()) < 15:
        raise RuntimeError(f"Capability card is too sparse in {svg_path.name}: {card_counts}")
    return {
        "semantic_card_groups": len(cards),
        "live_text_nodes": len(texts),
        "raster_nodes": len(images),
        "minimum_objects_per_card": min(card_counts.values()),
        "maximum_objects_per_card": max(card_counts.values()),
        "card_object_counts": card_counts,
        "missing_kinds": missing,
    }


def gallery_html(records):
    cards = "\n".join(
        f'''<article><h2>{record["title"]}</h2><p>{record["title_zh"]}</p><a href="assets/{record["svg"]}" target="_blank" rel="noopener"><img src="assets/{record["svg"]}" alt="{record["title"]}"></a></article>'''
        for record in records
    )
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Scientific Figure Capability Atlas</title><style>body{{margin:0;background:#eef1f4;color:#233042;font:16px/1.5 system-ui,sans-serif}}header{{padding:42px max(4vw,24px);background:#172536;color:white}}main{{display:grid;grid-template-columns:1fr;gap:30px;padding:30px;max-width:1500px;margin:auto}}article{{background:white;padding:22px;box-shadow:0 6px 24px #1c2b3a18}}h2{{margin:0;font-size:22px}}p{{margin:2px 0 14px;color:#6b7788}}img{{display:block;width:100%;height:auto;border:1px solid #d9e0e8;cursor:zoom-in}}</style></head><body><header><h1>Scientific Figure Capability Atlas</h1><p>64 deterministic, editable SVG demonstrations. Click a sheet to open its full-resolution SVG.</p></header><main>{cards}</main></body></html>'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    source_dir, recipe_dir, asset_dir = MODULE / "source", MODULE / "recipes", MODULE / "assets"
    for directory in (source_dir, recipe_dir, asset_dir):
        directory.mkdir(parents=True, exist_ok=True)
    blank = source_dir / "blank.png"
    if blank.exists() and not args.force:
        raise FileExistsError(f"Use --force to replace {blank}")
    Image.new("RGB", (WIDTH, HEIGHT), "white").save(blank)
    builder = ROOT / "skills" / "reconstruct-paper-figures" / "scripts" / "build_hybrid_svg.py"
    records = []
    for category in CATEGORIES:
        recipe_path = recipe_dir / f"{category['id']}.json"
        svg_path = asset_dir / f"{category['id']}.svg"
        if (recipe_path.exists() or svg_path.exists()) and not args.force:
            raise FileExistsError(f"Use --force to replace outputs for {category['id']}")
        write_text_lf(
            recipe_path,
            json.dumps(make_recipe(category), ensure_ascii=False, indent=2) + "\n",
        )
        command = [sys.executable, str(builder), str(recipe_path), str(svg_path)]
        if args.force:
            command.append("--force")
        subprocess.run(command, cwd=ROOT, check=True)
        audit = audit_svg(svg_path, category)
        records.append({
            "id": category["id"], "title": category["title"], "title_zh": category["title_zh"],
            "svg": svg_path.name, "recipe": recipe_path.name, "card_count": len(category["cards"]),
            "figure_families": [
                {
                    "title": title,
                    "subtitle": subtitle,
                    "kind": kind,
                    "real_task_planning_estimate": consumption_for(kind),
                }
                for title, subtitle, kind in category["cards"]
            ],
            "audit": audit, "svg_sha256": sha256(svg_path), "recipe_sha256": sha256(recipe_path),
        })
    manifest = {
        "format_version": 1, "generator": "reconstruct-paper-figures/build_hybrid_svg.py",
        "demonstration_scope": "synthetic deterministic capability atlas; not a source-paper fidelity claim",
        "consumption_model": {
            "atlas_generation": "0 model/API calls; deterministic local Python",
            "real_task_estimates": WORKLOAD_PROFILES,
            "disclaimer": "Planning ranges are not measured usage, a billing quote, or a guarantee.",
        },
        "category_count": len(CATEGORIES), "figure_family_count": len(list(all_cards())),
        "editable_svg_count": len(records), "records": records,
    }
    write_text_lf(
        MODULE / "capability-manifest.json",
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
    )
    write_text_lf(MODULE / "gallery.html", gallery_html(records))
    print(f"Generated {len(records)} SVG sheets covering {manifest['figure_family_count']} figure families.")


if __name__ == "__main__":
    main()
