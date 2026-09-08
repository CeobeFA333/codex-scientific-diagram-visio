from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import pdfplumber
import pypdfium2 as pdfium
from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfReader


CAPTION_RE = re.compile(
    r"^\s*((?:fig(?:ure)?\.?\s*\d+[A-Za-z]?)|(?:图\s*\d+))\s*[:：.、-]?\s*(.*)$",
    re.IGNORECASE,
)
VECTOR_OPERATOR_RE = re.compile(
    rb"(?<!\S)(?:m|l|c|v|y|h|re|S|s|f|F|f\*|B|B\*|b|b\*|n)(?!\S)"
)
TEXT_OPERATOR_RE = re.compile(rb"(?<!\S)(?:BT|ET|Tj|TJ|'|\")(?!\S)")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_inside_workspace(
    raw: Path, workspace: Path, *, must_exist: bool = False
) -> Path:
    root = workspace.resolve()
    candidate = raw if raw.is_absolute() else root / raw
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Path must stay inside workspace: {resolved}") from exc
    if must_exist and not resolved.exists():
        raise FileNotFoundError(resolved)
    return resolved


def safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return cleaned or "image"


def write_json(path: Path, payload: Any, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"Refusing to overwrite existing inventory: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def render_pages(
    pdf_path: Path, output_dir: Path, dpi: int, force: bool
) -> List[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    document = pdfium.PdfDocument(str(pdf_path))
    scale = dpi / 72.0
    outputs: List[Path] = []
    try:
        for page_index in range(len(document)):
            output = output_dir / f"page_{page_index + 1:04d}.png"
            if output.exists() and not force:
                raise FileExistsError(f"Refusing to overwrite page render: {output}")
            page = document[page_index]
            bitmap = page.render(scale=scale, rev_byteorder=True)
            bitmap.to_pil().convert("RGB").save(output, "PNG", optimize=True)
            outputs.append(output)
            bitmap.close()
            page.close()
    finally:
        document.close()
    return outputs


def make_contact_sheet(page_paths: Sequence[Path], output: Path, force: bool) -> None:
    if output.exists() and not force:
        raise FileExistsError(f"Refusing to overwrite contact sheet: {output}")
    thumb_width = 420
    margin = 24
    label_height = 30
    columns = 3
    thumbs: List[Image.Image] = []
    for path in page_paths:
        with Image.open(path) as opened:
            image = opened.convert("RGB")
            height = round(image.height * thumb_width / image.width)
            thumbs.append(
                image.resize((thumb_width, height), Image.Resampling.LANCZOS)
            )
    rows = math.ceil(len(thumbs) / columns)
    cell_height = max(image.height for image in thumbs) + label_height
    sheet = Image.new(
        "RGB",
        (
            columns * thumb_width + (columns + 1) * margin,
            rows * cell_height + (rows + 1) * margin,
        ),
        "white",
    )
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for index, image in enumerate(thumbs):
        row, column = divmod(index, columns)
        x = margin + column * (thumb_width + margin)
        y = margin + row * (cell_height + margin)
        draw.text((x, y), f"Page {index + 1}", fill="black", font=font)
        sheet.paste(image, (x, y + label_height))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, "PNG", optimize=True)


def content_bytes(page: Any) -> bytes:
    contents = page.get_contents()
    if contents is None:
        return b""
    if hasattr(contents, "get_data"):
        return contents.get_data()
    chunks: List[bytes] = []
    for item in contents:
        resolved = item.get_object() if hasattr(item, "get_object") else item
        if hasattr(resolved, "get_data"):
            chunks.append(resolved.get_data())
    return b"\n".join(chunks)


def extract_words(page: Any) -> List[Dict[str, Any]]:
    try:
        words = page.extract_words(
            use_text_flow=True,
            keep_blank_chars=False,
            extra_attrs=["fontname", "size"],
        )
    except (KeyError, TypeError):
        words = page.extract_words(use_text_flow=True, keep_blank_chars=False)
    normalized: List[Dict[str, Any]] = []
    for word in words:
        normalized.append(
            {
                "text": word.get("text", ""),
                "x0_pt": round(float(word.get("x0", 0)), 3),
                "top_pt": round(float(word.get("top", 0)), 3),
                "x1_pt": round(float(word.get("x1", 0)), 3),
                "bottom_pt": round(float(word.get("bottom", 0)), 3),
                "font": word.get("fontname"),
                "size_pt": round(float(word["size"]), 3)
                if word.get("size") is not None
                else None,
            }
        )
    return normalized


def image_placements(page: Any) -> List[Dict[str, Any]]:
    placements: List[Dict[str, Any]] = []
    for index, image in enumerate(page.images, start=1):
        x0 = float(image.get("x0", 0))
        x1 = float(image.get("x1", x0))
        top = float(image.get("top", 0))
        bottom = float(image.get("bottom", top))
        width_pt = max(0.0, x1 - x0)
        height_pt = max(0.0, bottom - top)
        source_size = image.get("srcsize") or (None, None)
        source_width = source_size[0]
        source_height = source_size[1]
        ppi_x = (
            float(source_width) / (width_pt / 72.0)
            if source_width and width_pt > 0
            else None
        )
        ppi_y = (
            float(source_height) / (height_pt / 72.0)
            if source_height and height_pt > 0
            else None
        )
        placements.append(
            {
                "placement_index": index,
                "pdf_object_name": str(image.get("name") or ""),
                "bbox_pt": [round(x0, 3), round(top, 3), round(x1, 3), round(bottom, 3)],
                "placed_width_pt": round(width_pt, 3),
                "placed_height_pt": round(height_pt, 3),
                "source_width_px": source_width,
                "source_height_px": source_height,
                "effective_ppi_x": round(ppi_x, 2) if ppi_x else None,
                "effective_ppi_y": round(ppi_y, 2) if ppi_y else None,
                "bits": image.get("bits"),
                "colorspace": str(image.get("colorspace")),
            }
        )
    return placements


def extract_caption_candidates(page_number: int, text: str) -> List[Dict[str, Any]]:
    captions: List[Dict[str, Any]] = []
    for line in text.splitlines():
        match = CAPTION_RE.match(line)
        if match:
            captions.append(
                {
                    "page": page_number,
                    "label": match.group(1).strip(),
                    "text": line.strip(),
                }
            )
    return captions


def classify_page(
    page_area_pt2: float,
    placements: Sequence[Dict[str, Any]],
    text_char_count: int,
    vector_operator_count: int,
) -> str:
    image_area = sum(
        item["placed_width_pt"] * item["placed_height_pt"] for item in placements
    )
    dominant_image = bool(placements) and image_area >= page_area_pt2 * 0.80
    if dominant_image and text_char_count < 5 and vector_operator_count < 5:
        return "raster_only_or_scanned"
    if placements and (text_char_count > 0 or vector_operator_count > 0):
        return "mixed_raster_text_vector"
    if placements:
        return "raster_objects_only"
    if text_char_count > 0 or vector_operator_count > 0:
        return "native_text_vector"
    return "empty_or_unclassified"


def extract_embedded_images(
    reader: PdfReader,
    output_dir: Path,
    placement_pages: Sequence[Sequence[Dict[str, Any]]],
    force: bool,
) -> List[Dict[str, Any]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    records: List[Dict[str, Any]] = []
    for page_number, page in enumerate(reader.pages, start=1):
        placements = list(placement_pages[page_number - 1])
        for image_index, image_file in enumerate(page.images, start=1):
            original_name = image_file.name or f"image_{image_index}.bin"
            suffix = Path(original_name).suffix.lower() or ".bin"
            output = output_dir / (
                f"p{page_number:04d}_{image_index:03d}_"
                f"{safe_name(Path(original_name).stem)}{suffix}"
            )
            if output.exists() and not force:
                raise FileExistsError(f"Refusing to overwrite extracted image: {output}")
            output.write_bytes(image_file.data)
            placement: Dict[str, Any] = {}
            object_stem = Path(original_name).stem
            for candidate in placements:
                if candidate["pdf_object_name"] == object_stem:
                    placement = candidate
                    break
            pil_image = image_file.image
            records.append(
                {
                    "page": page_number,
                    "page_image_index": image_index,
                    "pdf_object_name": original_name,
                    "file": output.name,
                    "format": pil_image.format or suffix.lstrip(".").upper(),
                    "mode": pil_image.mode,
                    "width_px": pil_image.width,
                    "height_px": pil_image.height,
                    "bytes": len(image_file.data),
                    "sha256": hashlib.sha256(image_file.data).hexdigest(),
                    **placement,
                }
            )
    return records


def write_csv(path: Path, records: Sequence[Dict[str, Any]], force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"Refusing to overwrite inventory CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for record in records for key in record})
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


def inventory_pdf(
    pdf_path: Path,
    output_root: Path,
    *,
    workspace: Path,
    dpi: int = 180,
    force: bool = False,
) -> Dict[str, Any]:
    if dpi < 72 or dpi > 1200:
        raise ValueError("DPI must be between 72 and 1200")
    pdf_path = resolve_inside_workspace(pdf_path, workspace, must_exist=True)
    output_root = resolve_inside_workspace(output_root, workspace)
    if output_root.exists() and any(output_root.iterdir()) and not force:
        raise FileExistsError(
            f"Output directory is not empty; choose a new directory or pass --force: {output_root}"
        )
    render_dir = output_root / "01_page_renders"
    image_dir = output_root / "02_embedded_images"
    inventory_dir = output_root / "03_inventory"
    output_root.mkdir(parents=True, exist_ok=True)

    # A BytesIO-backed reader avoids leaving a Windows file handle open after the
    # inventory returns while preserving the exact source bytes used for parsing.
    reader = PdfReader(io.BytesIO(pdf_path.read_bytes()))
    page_records: List[Dict[str, Any]] = []
    words_by_page: List[Dict[str, Any]] = []
    captions: List[Dict[str, Any]] = []
    placement_pages: List[List[Dict[str, Any]]] = []
    with pdfplumber.open(pdf_path) as plumber_document:
        for page_index, (reader_page, plumber_page) in enumerate(
            zip(reader.pages, plumber_document.pages), start=1
        ):
            width_pt = float(reader_page.mediabox.width)
            height_pt = float(reader_page.mediabox.height)
            text = reader_page.extract_text() or ""
            decoded = content_bytes(reader_page)
            placements = image_placements(plumber_page)
            words = extract_words(plumber_page)
            vector_count = len(VECTOR_OPERATOR_RE.findall(decoded))
            text_operator_count = len(TEXT_OPERATOR_RE.findall(decoded))
            record = {
                "page": page_index,
                "width_pt": round(width_pt, 3),
                "height_pt": round(height_pt, 3),
                "rotation_deg": int(reader_page.get("/Rotate", 0) or 0),
                "text_char_count": len(text.strip()),
                "word_count": len(words),
                "text_operator_count": text_operator_count,
                "vector_operator_count": vector_count,
                "image_placement_count": len(placements),
                "classification": classify_page(
                    width_pt * height_pt,
                    placements,
                    len(text.strip()),
                    vector_count,
                ),
            }
            page_records.append(record)
            placement_pages.append(placements)
            words_by_page.append({"page": page_index, "words": words})
            captions.extend(extract_caption_candidates(page_index, text))

    page_paths = render_pages(pdf_path, render_dir, dpi, force)
    make_contact_sheet(
        page_paths, inventory_dir / "page_contact_sheet.png", force
    )
    image_records = extract_embedded_images(
        reader, image_dir, placement_pages, force
    )
    summary = {
        "source_pdf": str(pdf_path),
        "source_sha256": sha256_file(pdf_path),
        "page_count": len(page_records),
        "embedded_image_count": len(image_records),
        "caption_candidate_count": len(captions),
        "page_render_dpi": dpi,
        "classifications": {
            name: sum(1 for page in page_records if page["classification"] == name)
            for name in sorted({page["classification"] for page in page_records})
        },
    }
    write_json(inventory_dir / "summary.json", summary, force)
    write_json(inventory_dir / "pages.json", page_records, force)
    write_json(inventory_dir / "text_words.json", words_by_page, force)
    write_json(inventory_dir / "image_placements.json", placement_pages, force)
    write_json(inventory_dir / "embedded_images.json", image_records, force)
    write_json(inventory_dir / "caption_candidates.json", captions, force)
    write_csv(inventory_dir / "embedded_images.csv", image_records, force)
    return summary


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Render a paper PDF, extract embedded images without screenshot recompression, "
            "and inventory native text/vector/raster objects."
        )
    )
    parser.add_argument("input_pdf", type=Path)
    parser.add_argument("output_root", type=Path)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--dpi", type=int, default=180)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    summary = inventory_pdf(
        args.input_pdf,
        args.output_root,
        workspace=args.workspace,
        dpi=args.dpi,
        force=args.force,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
