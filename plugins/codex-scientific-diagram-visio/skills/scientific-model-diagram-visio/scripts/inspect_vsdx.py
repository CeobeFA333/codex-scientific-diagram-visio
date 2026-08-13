#!/usr/bin/env python3
"""Static, read-only inspection of a Visio VSDX package.

This script cannot prove visual non-overlap or connector glue quality. It provides
package-level evidence that supplements reopen and screenshot-based QA.
"""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_xml(data: bytes, member: str) -> ET.Element | None:
    try:
        return ET.fromstring(data)
    except ET.ParseError as exc:
        print(f"warning: cannot parse {member}: {exc}", file=sys.stderr)
        return None


def page_metadata(zf: zipfile.ZipFile) -> list[dict[str, object]]:
    member = "visio/pages/pages.xml"
    if member not in zf.namelist():
        return []
    root = parse_xml(zf.read(member), member)
    if root is None:
        return []

    result: list[dict[str, object]] = []
    for page in (node for node in root.iter() if local_name(node.tag) == "Page"):
        cells = {
            cell.attrib.get("N"): cell.attrib.get("V")
            for cell in page.iter()
            if local_name(cell.tag) == "Cell"
        }
        result.append(
            {
                "id": page.attrib.get("ID"),
                "name": page.attrib.get("Name") or page.attrib.get("NameU"),
                "name_u": page.attrib.get("NameU"),
                "width_in": cells.get("PageWidth"),
                "height_in": cells.get("PageHeight"),
                "background": page.attrib.get("Background") == "1",
            }
        )
    return result


def inspect_page(zf: zipfile.ZipFile, member: str) -> dict[str, object]:
    root = parse_xml(zf.read(member), member)
    if root is None:
        return {"member": member, "parse_error": True}

    shapes = [node for node in root.iter() if local_name(node.tag) == "Shape"]
    texts: list[str] = []
    for node in root.iter():
        if local_name(node.tag) == "Text":
            value = "".join(node.itertext()).strip()
            if value:
                texts.append(" ".join(value.split()))

    return {
        "member": member,
        "shape_count": len(shapes),
        "group_count": sum(s.attrib.get("Type") == "Group" for s in shapes),
        "one_d_shape_count": sum(s.attrib.get("OneD") == "1" for s in shapes),
        "connection_record_count": sum(
            1 for node in root.iter() if local_name(node.tag) == "Connect"
        ),
        "foreign_data_count": sum(
            1 for node in root.iter() if local_name(node.tag) == "ForeignData"
        ),
        "text_count": len(texts),
        "texts": texts,
    }


def inspect(path: Path) -> dict[str, object]:
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        page_members: list[str] = []
        for name in names:
            if not name.startswith("visio/pages/page") or not name.endswith(".xml"):
                continue
            stem = Path(name).stem
            if stem.startswith("page") and stem[4:].isdigit():
                page_members.append(name)
        page_members.sort(key=lambda name: int(Path(name).stem[4:]))
        pages = [inspect_page(zf, member) for member in page_members]
        media = sorted(name for name in names if name.startswith("visio/media/"))
        masters = [
            name
            for name in names
            if name.startswith("visio/masters/master") and name.endswith(".xml")
        ]
        return {
            "path": str(path.resolve()),
            "package_size_bytes": path.stat().st_size,
            "page_count": len(page_members),
            "page_metadata": page_metadata(zf),
            "pages": pages,
            "master_part_count": len(masters),
            "embedded_media_count": len(media),
            "embedded_media": media,
            "totals": {
                "shapes": sum(int(p.get("shape_count", 0)) for p in pages),
                "groups": sum(int(p.get("group_count", 0)) for p in pages),
                "one_d_shapes": sum(int(p.get("one_d_shape_count", 0)) for p in pages),
                "connection_records": sum(
                    int(p.get("connection_record_count", 0)) for p in pages
                ),
                "foreign_data": sum(
                    int(p.get("foreign_data_count", 0)) for p in pages
                ),
                "texts": sum(int(p.get("text_count", 0)) for p in pages),
            },
            "limitations": [
                "Static package inspection cannot detect visual overlaps or clipping.",
                "Connector counts do not prove both endpoints are correctly glued.",
                "Reopen, selection/edit, and exported-image inspection remain mandatory.",
            ],
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vsdx", type=Path, help="Path to the .vsdx file")
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    parser.add_argument(
        "--require-single-page", action="store_true", help="Fail unless one page remains"
    )
    parser.add_argument(
        "--forbid-raster",
        action="store_true",
        help="Fail if embedded media or ForeignData objects are present",
    )
    args = parser.parse_args()

    if not args.vsdx.is_file():
        parser.error(f"file not found: {args.vsdx}")
    if args.vsdx.suffix.lower() != ".vsdx":
        parser.error("input must have a .vsdx extension")

    try:
        report = inspect(args.vsdx)
    except zipfile.BadZipFile:
        print("error: input is not a valid VSDX/ZIP package", file=sys.stderr)
        return 2

    failures: list[str] = []
    if args.require_single_page and report["page_count"] != 1:
        failures.append(f"expected one page, found {report['page_count']}")
    if args.forbid_raster:
        totals = report["totals"]
        if report["embedded_media_count"] or totals["foreign_data"]:
            failures.append(
                "raster/foreign data present: "
                f"media={report['embedded_media_count']}, "
                f"foreign_data={totals['foreign_data']}"
            )
    report["failures"] = failures
    report["passed_requested_checks"] = not failures

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"VSDX: {report['path']}")
        print(f"Pages: {report['page_count']}")
        print(f"Page metadata: {report['page_metadata']}")
        print(f"Totals: {report['totals']}")
        print(f"Embedded media: {report['embedded_media_count']}")
        for page in report["pages"]:
            print(
                f"- {page['member']}: shapes={page.get('shape_count', 0)}, "
                f"groups={page.get('group_count', 0)}, "
                f"one_d={page.get('one_d_shape_count', 0)}, "
                f"connections={page.get('connection_record_count', 0)}, "
                f"foreign_data={page.get('foreign_data_count', 0)}, "
                f"texts={page.get('text_count', 0)}"
            )
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
