#!/usr/bin/env python3
"""Compose the evidence-to-Visio demo from real Visio screenshots.

The Visio frames are captured by build_transformer_visio_demo.ps1 while
Microsoft Visio is visible. This script only adds explanatory title cards and
captions; it does not simulate or redraw the Visio UI.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


WIDTH, HEIGHT = 1280, 720
NAVY = (12, 31, 58)
BLUE = (36, 74, 143)
TEAL = (43, 156, 152)
ORANGE = (230, 162, 60)
INK = (22, 32, 43)
MUTED = (96, 112, 128)
WHITE = (255, 255, 255)
LIGHT = (244, 247, 251)
LANCZOS = getattr(getattr(Image, "Resampling", Image), "LANCZOS")


def font_path(bold: bool = False, mono: bool = False) -> str | None:
    candidates: list[Path] = []
    windir = Path(os.environ.get("WINDIR", "Windows")) / "Fonts"
    if mono:
        candidates.extend([windir / "consola.ttf", windir / "cour.ttf"])
    elif bold:
        candidates.extend([windir / "segoeuib.ttf", windir / "arialbd.ttf"])
    else:
        candidates.extend([windir / "segoeui.ttf", windir / "arial.ttf"])
    candidates.extend(
        [
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        ]
    )
    return str(next((path for path in candidates if path.exists()), "")) or None


def get_font(size: int, bold: bool = False, mono: bool = False) -> ImageFont.ImageFont:
    path = font_path(bold=bold, mono=mono)
    return ImageFont.truetype(path, size) if path else ImageFont.load_default()


def fit_inside(image: Image.Image, width: int, height: int, background=WHITE) -> Image.Image:
    image = image.convert("RGB")
    ratio = min(width / image.width, height / image.height)
    resized = image.resize((max(1, int(image.width * ratio)), max(1, int(image.height * ratio))), LANCZOS)
    canvas = Image.new("RGB", (width, height), background)
    canvas.paste(resized, ((width - resized.width) // 2, (height - resized.height) // 2))
    return canvas


def centered(draw: ImageDraw.ImageDraw, text: str, y: int, font, fill=INK) -> None:
    width, _ = draw.textsize(text, font=font)
    draw.text(((WIDTH - width) // 2, y), text, font=font, fill=fill)


def title_card() -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), NAVY)
    draw = ImageDraw.Draw(image)
    for x in range(WIDTH):
        blend = x / WIDTH
        color = (
            int(NAVY[0] * (1 - blend) + BLUE[0] * blend),
            int(NAVY[1] * (1 - blend) + BLUE[1] * blend),
            int(NAVY[2] * (1 - blend) + BLUE[2] * blend),
        )
        draw.line((x, 0, x, HEIGHT), fill=color)
    draw.rounded_rectangle((95, 90, 1185, 630), radius=34, outline=(118, 169, 224), width=3)
    centered(draw, "CODEX SCIENTIFIC DIAGRAM WORKFLOW", 135, get_font(20, bold=True), (154, 205, 255))
    centered(draw, "Paper & Code  →  Image Reference  →  Editable Visio", 225, get_font(38, bold=True), WHITE)
    centered(draw, "A real Transformer Encoder reconstruction", 300, get_font(26), (212, 228, 246))
    steps = [("01", "READ", TEAL), ("02", "DESIGN", ORANGE), ("03", "BUILD", (126, 165, 220)), ("04", "VERIFY", (153, 207, 122))]
    left = 205
    for index, (number, label, color) in enumerate(steps):
        x = left + index * 225
        draw.ellipse((x, 410, x + 74, 484), fill=color)
        centered_number = get_font(20, bold=True)
        tw, th = draw.textsize(number, font=centered_number)
        draw.text((x + 37 - tw / 2, 447 - th / 2), number, font=centered_number, fill=NAVY)
        draw.text((x - 2, 505), label, font=get_font(17, bold=True), fill=WHITE)
        if index < len(steps) - 1:
            draw.line((x + 90, 447, x + 200, 447), fill=(126, 158, 195), width=4)
            draw.polygon([(x + 200, 447), (x + 188, 440), (x + 188, 454)], fill=(126, 158, 195))
    return image


def evidence_card() -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), LIGHT)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, WIDTH, 86), fill=NAVY)
    draw.text((54, 24), "1  Read the architecture and freeze the model contract", font=get_font(28, bold=True), fill=WHITE)
    draw.rounded_rectangle((54, 122, 610, 650), radius=22, fill=WHITE, outline=(198, 211, 225), width=2)
    draw.text((86, 154), "Evidence", font=get_font(23, bold=True), fill=BLUE)
    draw.text((86, 208), "Attention Is All You Need", font=get_font(25, bold=True), fill=INK)
    draw.text((86, 250), "Vaswani et al. · 2017", font=get_font(18), fill=MUTED)
    draw.multiline_text(
        (86, 315),
        "• Original Transformer paper\n• Official PyTorch encoder-layer API\n• Tensor dimensions checked before drawing",
        font=get_font(19), fill=INK, spacing=16,
    )
    draw.text((86, 535), "Sources", font=get_font(16, bold=True), fill=BLUE)
    draw.text((86, 572), "arxiv.org/abs/1706.03762", font=get_font(15, mono=True), fill=MUTED)
    draw.text((86, 606), "pytorch.org/.../TransformerEncoderLayer", font=get_font(15, mono=True), fill=MUTED)
    draw.rounded_rectangle((646, 122, 1226, 650), radius=22, fill=WHITE, outline=(198, 211, 225), width=2)
    draw.text((680, 154), "Frozen contract", font=get_font(23, bold=True), fill=TEAL)
    rows = [
        ("Input", "Token IDs [B × L]"),
        ("Embedding", "[B × L × 512]"),
        ("Attention", "8 heads · d_model = 512"),
        ("FFN", "512 → 2048 → 512 · ReLU"),
        ("Normalization", "2 × residual + LayerNorm"),
        ("Depth", "N = 6 encoder layers"),
        ("Output", "[B × L × 512]"),
    ]
    y = 216
    for label, value in rows:
        draw.rounded_rectangle((680, y, 1192, y + 48), radius=11, fill=(245, 249, 252))
        draw.text((698, y + 13), label, font=get_font(15, bold=True), fill=BLUE)
        draw.text((840, y + 13), value, font=get_font(15), fill=INK)
        y += 58
    return image


def reference_card(reference_path: Path) -> Image.Image:
    reference = fit_inside(Image.open(reference_path), 1140, 555, WHITE)
    image = Image.new("RGB", (WIDTH, HEIGHT), LIGHT)
    image.paste(reference, (70, 112))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, WIDTH, 86), fill=NAVY)
    draw.text((54, 24), "2  Generate a visual reference with Codex ImageGen", font=get_font(28, bold=True), fill=WHITE)
    draw.rounded_rectangle((70, 112, 1210, 667), radius=18, outline=(198, 211, 225), width=2)
    badge = "REFERENCE ONLY — never embedded in the VSDX"
    bw, _ = draw.textsize(badge, font=get_font(15, bold=True))
    draw.rounded_rectangle((WIDTH - bw - 95, 620, WIDTH - 70, 655), radius=12, fill=(255, 247, 224))
    draw.text((WIDTH - bw - 82, 629), badge, font=get_font(15, bold=True), fill=(145, 92, 14))
    return image


def caption_visio(frame_path: Path, step: int, total: int, caption: str) -> Image.Image:
    image = Image.open(frame_path).convert("RGB").resize((WIDTH, HEIGHT), LANCZOS)
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rectangle((0, 0, WIDTH, 76), fill=(12, 31, 58, 224))
    draw.rounded_rectangle((26, 17, 132, 59), radius=15, fill=(43, 156, 152, 245))
    draw.text((47, 27), f"{step:02d}/{total:02d}", font=get_font(17, bold=True), fill=WHITE)
    draw.text((158, 23), caption, font=get_font(22, bold=True), fill=WHITE)
    draw.rectangle((0, HEIGHT - 38, WIDTH, HEIGHT), fill=(12, 31, 58, 210))
    draw.text((32, HEIGHT - 29), "REAL MICROSOFT VISIO UI · NATIVE SHAPES · GLUED CONNECTORS", font=get_font(15, bold=True), fill=(202, 225, 247))
    return Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")


def comparison_card(reference_path: Path, final_path: Path) -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), LIGHT)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, WIDTH, 86), fill=NAVY)
    draw.text((54, 24), "4  Compare, reopen, and verify editability", font=get_font(28, bold=True), fill=WHITE)
    left = fit_inside(Image.open(reference_path), 555, 475, WHITE)
    right = fit_inside(Image.open(final_path), 555, 475, WHITE)
    image.paste(left, (60, 155))
    image.paste(right, (665, 155))
    draw.rounded_rectangle((60, 155, 615, 630), radius=18, outline=(198, 211, 225), width=2)
    draw.rounded_rectangle((665, 155, 1220, 630), radius=18, outline=(43, 156, 152), width=3)
    draw.text((60, 112), "ImageGen design reference", font=get_font(19, bold=True), fill=ORANGE)
    draw.text((665, 112), "Native editable Visio output", font=get_font(19, bold=True), fill=TEAL)
    centered(draw, "105 shapes · 16 editable groups · 24 connection records · 0 embedded images", 659, get_font(18, bold=True), BLUE)
    return image


def end_card() -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), NAVY)
    draw = ImageDraw.Draw(image)
    centered(draw, "From scientific evidence to an editable .vsdx", 180, get_font(41, bold=True), WHITE)
    centered(draw, "The reference image guides style. The verified model contract controls truth.", 258, get_font(22), (206, 224, 243))
    draw.rounded_rectangle((306, 355, 974, 445), radius=24, fill=TEAL)
    centered(draw, "github.com/CeobeFA333/codex-scientific-diagram-visio", 383, get_font(20, bold=True), WHITE)
    centered(draw, "VSDX · PDF · PNG · reproducible Visio automation script", 505, get_font(19), (166, 197, 227))
    return image


def to_palette(image: Image.Image) -> Image.Image:
    return image.convert("P", palette=Image.ADAPTIVE, colors=192)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    manifest = json.loads((args.build_dir / "frame-manifest.json").read_text(encoding="utf-8-sig"))
    frames: list[Image.Image] = [title_card(), evidence_card(), reference_card(args.reference)]
    durations = [1800, 2200, 2200]
    visio_entries = [entry for entry in manifest if isinstance(entry, dict)]
    for index, entry in enumerate(visio_entries, start=1):
        frames.append(caption_visio(Path(entry["File"]), index, len(visio_entries), entry["Label"]))
        durations.append(900 if index < 8 else 1500)
    frames.append(comparison_card(args.reference, args.build_dir / "transformer-encoder-demo.png"))
    durations.append(2400)
    frames.append(end_card())
    durations.append(2200)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    paletted = [to_palette(frame) for frame in frames]
    paletted[0].save(
        args.output,
        save_all=True,
        append_images=paletted[1:],
        duration=durations,
        loop=0,
        optimize=True,
        disposal=2,
    )
    print(f"Wrote {args.output} ({args.output.stat().st_size} bytes, {len(frames)} frames)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
