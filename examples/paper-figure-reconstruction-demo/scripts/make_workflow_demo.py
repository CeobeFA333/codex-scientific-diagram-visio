#!/usr/bin/env python3
"""Build the evidence-driven paper-figure reconstruction demo GIF."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Tuple

from PIL import Image, ImageDraw, ImageFont


Box = Tuple[int, int, int, int]
SIZE = (1280, 720)
NAVY = (12, 31, 58)
BLUE = (36, 74, 143)
TEAL = (43, 156, 152)
ORANGE = (230, 162, 60)
INK = (28, 42, 61)
MUTED = (89, 105, 126)
PAPER = (246, 249, 253)
WHITE = (255, 255, 255)
GREEN = (47, 140, 97)
RED = (190, 68, 73)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        Path("C:/Windows/Fonts/seguisb.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def fit_text(draw: ImageDraw.ImageDraw, text: str, max_width: int, start: int, bold: bool = False) -> ImageFont.ImageFont:
    size = start
    while size > 12:
        chosen = font(size, bold)
        if draw.textbbox((0, 0), text, font=chosen)[2] <= max_width:
            return chosen
        size -= 1
    return font(12, bold)


def rounded(
    draw,
    box,
    fill,
    style=None,
) -> None:
    if style is None:
        style = (None, 1, 18)
    outline, width, radius = style
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def header(draw: ImageDraw.ImageDraw, kicker: str, title: str, subtitle: str) -> None:
    draw.text((58, 36), kicker.upper(), font=font(18, True), fill=TEAL)
    draw.text((58, 68), title, font=fit_text(draw, title, 1164, 44, True), fill=NAVY)
    draw.text((60, 126), subtitle, font=fit_text(draw, subtitle, 1158, 22), fill=MUTED)
    draw.line((58, 165, 1222, 165), fill=(210, 220, 232), width=2)


def footer(draw: ImageDraw.ImageDraw, text: str) -> None:
    draw.line((58, 670, 1222, 670), fill=(215, 224, 235), width=1)
    draw.text((58, 683), text, font=font(15), fill=MUTED)


def canvas() -> Tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", SIZE, PAPER)
    return image, ImageDraw.Draw(image)


def title_card() -> Image.Image:
    image = Image.new("RGB", SIZE, NAVY)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((60, 58, 1220, 662), radius=34, fill=(18, 43, 76), outline=(68, 100, 142), width=2)
    draw.text((98, 102), "CODEX · SCIENTIFIC FIGURE WORKFLOW", font=font(18, True), fill=(103, 208, 200))
    draw.text((98, 181), "PAPER FIGURES,", font=font(61, True), fill=WHITE)
    draw.text((98, 256), "REBUILT AS EDITABLE EVIDENCE", font=fit_text(draw, "REBUILT AS EDITABLE EVIDENCE", 1040, 55, True), fill=WHITE)
    draw.rounded_rectangle((98, 373, 1145, 465), radius=18, fill=(27, 57, 96))
    draw.text((126, 399), "PDF inventory  →  hybrid vectors  →  source-data charts  →  roundtrip QA", font=fit_text(draw, "PDF inventory  →  hybrid vectors  →  source-data charts  →  roundtrip QA", 990, 25), fill=(219, 231, 244))
    draw.text((100, 549), "v1.3.1 · MIT · real outputs and audit evidence", font=font(24, True), fill=(244, 184, 80))
    return image


def workflow_card() -> Image.Image:
    image, draw = canvas()
    header(draw, "Workflow", "One contract from source to delivery", "Every transition produces an inspectable artifact or a blocking decision.")
    labels = [
        ("01", "INVENTORY", "PDF text, vectors, images, captions"),
        ("02", "CLASSIFY", "editable geometry vs scientific pixels"),
        ("03", "REBUILD", "live text, paths, charts, atomic rasters"),
        ("04", "VERIFY", "hashes, reopen audits, publication gate"),
    ]
    x_positions = [58, 354, 650, 946]
    colors = [BLUE, TEAL, ORANGE, GREEN]
    for index, (number, label, detail) in enumerate(labels):
        x = x_positions[index]
        rounded(draw, (x, 225, x + 248, 518), WHITE, ((208, 219, 232), 2, 24))
        draw.ellipse((x + 24, 247, x + 84, 307), fill=colors[index])
        draw.text((x + 42, 263), number, font=font(17, True), fill=WHITE)
        draw.text((x + 24, 341), label, font=font(25, True), fill=NAVY)
        words = detail.split(" ")
        lines: List[str] = []
        current = ""
        for word in words:
            probe = (current + " " + word).strip()
            if draw.textbbox((0, 0), probe, font=font(18))[2] > 198 and current:
                lines.append(current)
                current = word
            else:
                current = probe
        lines.append(current)
        for line_no, line in enumerate(lines):
            draw.text((x + 24, 391 + 28 * line_no), line, font=font(18), fill=MUTED)
        if index < 3:
            draw.line((x + 251, 370, x + 291, 370), fill=colors[index], width=5)
            draw.polygon([(x + 291, 370), (x + 278, 362), (x + 278, 378)], fill=colors[index])
    footer(draw, "Fail closed: unresolved data, scale-bar, or human-review questions remain visible blockers.")
    return image


def contain(source: Image.Image, box: Box) -> Tuple[Image.Image, Tuple[int, int]]:
    x0, y0, x1, y1 = box
    maximum = (x1 - x0, y1 - y0)
    resampling = getattr(Image, "Resampling", Image).LANCZOS
    copy = source.copy()
    copy.thumbnail(maximum, resampling)
    return copy, (x0 + (maximum[0] - copy.width) // 2, y0 + (maximum[1] - copy.height) // 2)


def artifact_card(source: Image.Image, content: Dict[str, str]) -> Image.Image:
    image, draw = canvas()
    header(draw, content["kicker"], content["title"], content["subtitle"])
    rounded(draw, (58, 190, 1222, 609), WHITE, ((204, 216, 230), 2, 18))
    preview, position = contain(source, (82, 207, 1198, 546))
    image.paste(preview, position)
    rounded(draw, (82, 557, 1198, 596), (233, 242, 250), (None, 1, 10))
    metric = content["metric"]
    draw.text((98, 565), metric, font=fit_text(draw, metric, 1084, 17, True), fill=BLUE)
    footer(draw, content["attribution"])
    return image


def evidence_card(evidence: Dict[str, object], preview: Image.Image) -> Image.Image:
    image, draw = canvas()
    header(draw, "Illustrator evidence", "Editable through three reopen stages", "SVG import, AI reopen, and editable-PDF reopen report the same object counts.")
    preview_copy, position = contain(preview, (64, 205, 602, 581))
    rounded(draw, (58, 194, 614, 594), WHITE, ((204, 216, 230), 2, 18))
    image.paste(preview_copy, position)
    counts = evidence["verified_counts_each_stage"]
    metrics = [
        ("TEXT", str(counts["text_frames"]), TEAL),
        ("PATHS", str(counts["path_items"]), BLUE),
        ("GROUPS", str(counts["group_items"]), ORANGE),
        ("PLACED", str(counts["placed_items"]), GREEN),
        ("RASTER", str(counts["raster_items"]), BLUE),
        ("WARNINGS", str(counts["warnings"]), GREEN),
    ]
    for index, (label, value, color) in enumerate(metrics):
        column = index % 2
        row = index // 2
        x = 650 + column * 271
        y = 211 + row * 118
        rounded(draw, (x, y, x + 244, y + 94), WHITE, ((207, 219, 232), 2, 16))
        draw.text((x + 18, y + 13), label, font=font(15, True), fill=MUTED)
        draw.text((x + 18, y + 38), value, font=font(36, True), fill=color)
    rounded(draw, (650, 575, 1165, 626), (255, 241, 219), (None, 1, 12))
    draw.text((669, 590), "Publication gate: BLOCKED · 6 declared blockers", font=font(18, True), fill=RED)
    footer(draw, "Illustrator 29.8.2 · Times New Roman 8.5 pt · 3 linked scientific-image atoms · 0 raster items")
    return image


def cleanup_card(audit: Dict[str, object]) -> Image.Image:
    image, draw = canvas()
    header(draw, "Reviewed OCR cleanup", "Bounded edits, independently audited", "Only approved text masks may change; protected apparatus pixels remain untouched.")
    selected = audit["mask"]["selected_pixels"]
    changed = audit["pixel_changes"]["changed_pixels"]
    outside = audit["pixel_changes"]["outside_mask_changed_pixels"]
    residual = audit["heuristics"]["residual_pixel_count"]
    items = [
        ("MASKED PIXELS", f"{selected:,}", "2.23% of image", BLUE),
        ("CHANGED INSIDE", f"{changed:,}", "bounded by reviewed mask", TEAL),
        ("CHANGED OUTSIDE", f"{outside:,}", "protected pixels preserved", GREEN),
        ("RESIDUAL TEXT", f"{residual:,}", "heuristic scan", ORANGE),
    ]
    for index, (label, value, note, color) in enumerate(items):
        x = 58 + (index % 2) * 578
        y = 208 + (index // 2) * 177
        rounded(draw, (x, y, x + 544, y + 145), WHITE, ((205, 218, 232), 2, 20))
        draw.text((x + 24, y + 20), label, font=font(16, True), fill=MUTED)
        draw.text((x + 24, y + 50), value, font=font(45, True), fill=color)
        draw.text((x + 190, y + 76), note, font=font(18), fill=INK)
    rounded(draw, (58, 576, 1200, 630), (255, 241, 219), (None, 1, 12))
    draw.text((80, 591), "Machine audit passed · human review at 200–400% is still required", font=font(21, True), fill=RED)
    footer(draw, "Safe cleanup is non-generative: no invented scientific pixels and no automatic publication approval.")
    return image


def capability_card() -> Image.Image:
    image, draw = canvas()
    header(draw, "Current capability", "What v1.3.1 can actually deliver", "One plugin, three focused skills, explicit editor and evidence boundaries.")
    rows = [
        ("PDF INVENTORY", "text · vectors · images · placements · captions · effective PPI", "VALIDATED"),
        ("HYBRID REBUILD", "editable SVG + live text + minimal scientific raster atoms", "VALIDATED"),
        ("STATISTICAL FIGURES", "publisher source data → editable plots; missing groups stay blocked", "REVIEW"),
        ("TEXT CLEANUP", "reviewed masks → bounded cleanup → live-text overlay → pixel audit", "REVIEW"),
        ("ROUNDTRIP QA", "SVG import → AI reopen → editable PDF reopen → hash-bound evidence", "WINDOWS"),
        ("DIAGRAM BACKENDS", "native Visio VSDX plus draw.io framework geometry", "MIXED"),
    ]
    for index, (name, detail, status) in enumerate(rows):
        y = 195 + index * 72
        fill = WHITE if index % 2 == 0 else (238, 244, 250)
        rounded(draw, (58, y, 1222, y + 56), fill, (None, 1, 10))
        draw.text((78, y + 16), name, font=font(16, True), fill=NAVY)
        draw.text((302, y + 16), detail, font=fit_text(draw, detail, 735, 17), fill=INK)
        badge_color = GREEN if status == "VALIDATED" else ORANGE
        rounded(draw, (1063, y + 11, 1204, y + 45), badge_color, (None, 1, 15))
        draw.text((1080, y + 19), status, font=fit_text(draw, status, 106, 14, True), fill=WHITE)
    footer(draw, "Portable core: Agent Skills clients · AI/PDF roundtrip: Illustrator 29.8.2 on Windows · VSDX: Windows + Visio")
    return image


def boundary_card(evidence: Dict[str, object]) -> Image.Image:
    image, draw = canvas()
    header(draw, "Publication gate", "Honest outputs include unresolved blockers", "Passing structural audits never substitutes for scientific or editorial judgment.")
    blockers = evidence["remaining_blockers"]
    readable = [
        "Publisher source data missing for one distance group",
        "One panel geometry is not source-data bound",
        "Scale-bar calibration or baked-in state remains unresolved",
        "P-value label assignment needs scientific review",
        "Human visual and typography approval is pending",
    ]
    for index, label in enumerate(readable):
        y = 210 + index * 72
        draw.ellipse((66, y + 5, 92, y + 31), fill=RED)
        draw.text((72, y + 4), "!", font=font(19, True), fill=WHITE)
        draw.text((111, y + 2), label, font=font(22, True if index == 0 else False), fill=INK)
    rounded(draw, (58, 592, 1222, 642), (234, 239, 247), (None, 1, 12))
    draw.text((80, 607), f"Machine-readable status: publication_ready=false · declared blockers={len(blockers)}", font=font(19, True), fill=NAVY)
    footer(draw, "The workflow stops at the gate instead of silently fabricating missing evidence.")
    return image


def end_card() -> Image.Image:
    image = Image.new("RGB", SIZE, NAVY)
    draw = ImageDraw.Draw(image)
    draw.text((72, 90), "THREE FOCUSED SKILLS.", font=font(48, True), fill=WHITE)
    draw.text((72, 157), "ONE EVIDENCE CHAIN.", font=font(48, True), fill=(106, 208, 201))
    rounded(draw, (72, 269, 1208, 450), (20, 49, 84), ((64, 101, 145), 2, 24))
    draw.text((108, 303), "Prompting · Native Visio · Paper figure reconstruction", font=fit_text(draw, "Prompting · Native Visio · Paper figure reconstruction", 1058, 30, True), fill=WHITE)
    draw.text((108, 363), "Editable outputs, reproducible audits, explicit publication blockers", font=fit_text(draw, "Editable outputs, reproducible audits, explicit publication blockers", 1058, 25), fill=(219, 231, 244))
    draw.text((72, 528), "github.com/CeobeFA333/codex-scientific-diagram-visio", font=fit_text(draw, "github.com/CeobeFA333/codex-scientific-diagram-visio", 1136, 28, True), fill=(244, 184, 80))
    draw.text((72, 594), "MIT License · v1.3.1", font=font(22, True), fill=WHITE)
    return image


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--simpli-preview", type=Path, required=True)
    parser.add_argument("--stats-preview", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--cleanup-audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path.cwd(),
        help="Boundary that must contain every input and the output",
    )
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def resolve_inside_workspace(raw: Path, workspace: Path, must_exist: bool) -> Path:
    candidate = raw.resolve() if raw.is_absolute() else (Path.cwd() / raw).resolve()
    try:
        candidate.relative_to(workspace)
    except ValueError as exc:
        raise ValueError("Path escapes the declared workspace: %s" % raw) from exc
    if must_exist and not candidate.is_file():
        raise FileNotFoundError("Input file does not exist: %s" % raw)
    return candidate


def build_frames(artifacts: Dict[str, object]) -> List[Image.Image]:
    simpli = artifacts["simpli"]
    stats = artifacts["stats"]
    evidence = artifacts["evidence"]
    cleanup = artifacts["cleanup"]
    simpli_content = {
        "kicker": "Real reconstructed artifact",
        "title": "SIMPLI Figure 4 · hybrid editable reconstruction",
        "subtitle": (
            "Editable vectors and live text preserve three continuous-tone "
            "microscopy regions as atomic evidence."
        ),
        "metric": "10 panels · 7 vector/data-bound panels · 3 linked scientific-image atoms",
        "attribution": (
            "Adapted from Bortolomeazzi et al. (2022), "
            "Nature Communications 13:781 · CC BY 4.0"
        ),
    }
    stats_content = {
        "kicker": "Real reconstructed artifact",
        "title": "TOmicsVis Figure 2 · editable statistical suite",
        "subtitle": (
            "A shared design grammar spans distribution, survival, heatmap, "
            "and embedding plots."
        ),
        "metric": "Q-Q · box · violin · Kaplan–Meier · heatmap · PCA · t-SNE · Ward",
        "attribution": "Adapted from Miao et al. (2023), iMeta e137 · CC BY 4.0",
    }
    return [
        title_card(),
        workflow_card(),
        artifact_card(simpli, simpli_content),
        artifact_card(stats, stats_content),
        cleanup_card(cleanup),
        evidence_card(evidence, simpli),
        capability_card(),
        boundary_card(evidence),
        end_card(),
    ]


def main() -> int:
    args = parse_args()
    workspace = args.workspace.resolve()
    if not workspace.is_dir():
        raise NotADirectoryError("Workspace does not exist: %s" % workspace)
    simpli_path = resolve_inside_workspace(args.simpli_preview, workspace, True)
    stats_path = resolve_inside_workspace(args.stats_preview, workspace, True)
    evidence_path = resolve_inside_workspace(args.evidence, workspace, True)
    cleanup_path = resolve_inside_workspace(args.cleanup_audit, workspace, True)
    output_path = resolve_inside_workspace(args.output, workspace, False)
    if output_path.suffix.lower() != ".gif":
        raise ValueError("Output must be a .gif file")
    if output_path.exists() and not args.force:
        raise FileExistsError("Refusing to overwrite %s; pass --force" % output_path)
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    cleanup = json.loads(cleanup_path.read_text(encoding="utf-8"))
    if evidence.get("publication_ready") is not False:
        raise ValueError("Demo expects an explicitly blocked publication gate")
    if cleanup.get("pixel_changes", {}).get("outside_mask_changed_pixels") != 0:
        raise ValueError("Cleanup audit does not prove zero outside-mask changes")
    simpli = Image.open(simpli_path).convert("RGB")
    stats = Image.open(stats_path).convert("RGB")
    frames = build_frames(
        {
            "simpli": simpli,
            "stats": stats,
            "evidence": evidence,
            "cleanup": cleanup,
        }
    )
    durations = [1800, 2100, 2600, 2500, 2300, 2700, 2800, 2600, 2300]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        output_path,
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        optimize=True,
        disposal=2,
    )
    print("Created %s with %d evidence-driven frames." % (output_path, len(frames)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
