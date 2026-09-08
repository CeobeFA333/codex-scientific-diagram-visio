#!/usr/bin/env python3
"""Bind one SVG/AI/editable-PDF Illustrator roundtrip to hash-checked evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Sequence


def fail(message: str) -> None:
    raise ValueError(message)


def resolve_file(raw: Path, workspace: Path) -> Path:
    workspace = workspace.resolve()
    path = raw if raw.is_absolute() else workspace / raw
    path = path.resolve()
    try:
        path.relative_to(workspace)
    except ValueError:
        fail("path escapes workspace: %s" % path)
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def resolve_output(raw: Path, workspace: Path, force: bool) -> Path:
    workspace = workspace.resolve()
    path = raw if raw.is_absolute() else workspace / raw
    path = path.resolve()
    try:
        path.relative_to(workspace)
    except ValueError:
        fail("output escapes workspace: %s" % path)
    if path.exists() and not force:
        fail("output exists; pass --force to replace: %s" % path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        fail("JSON root must be an object: %s" % path)
    return payload


def relative(path: Path, base: Path) -> str:
    return os.path.relpath(str(path), str(base)).replace("\\", "/")


def same_path(left: Path, right: Path) -> bool:
    return os.path.normcase(str(left.resolve())) == os.path.normcase(str(right.resolve()))


def finite_float(value: Any, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        fail("invalid numeric value for %s" % label)
    if not math.isfinite(number):
        fail("non-finite numeric value for %s" % label)
    return number


def atomic_write(path: Path, payload: bytes) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(payload)
    os.replace(str(temporary), str(path))


def build_manifest(
    source_svg: Path,
    ai: Path,
    pdf: Path,
    stage_audits: Iterable[Path],
    structural_audit: Path,
    render: Path,
    output: Path,
    workspace: Path,
    expected_text_count: int,
    expected_raster_count: int,
    font_family: str,
    font_size_pt: float,
    force: bool = False,
    expected_placed_count: int = 0,
    placement_manifest: Optional[Path] = None,
    expected_path_count: Optional[int] = None,
    expected_group_count: Optional[int] = None,
    remaining_blockers: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    workspace = workspace.resolve()
    source_svg = resolve_file(source_svg, workspace)
    ai = resolve_file(ai, workspace)
    pdf = resolve_file(pdf, workspace)
    audit_paths = [resolve_file(path, workspace) for path in stage_audits]
    structural_audit = resolve_file(structural_audit, workspace)
    render = resolve_file(render, workspace)
    placement_path = resolve_file(placement_manifest, workspace) if placement_manifest else None
    output = resolve_output(output, workspace, force)
    if len(audit_paths) != 3:
        fail("exactly three Illustrator stage audits are required")
    protected_inputs = [source_svg, ai, pdf, structural_audit, render] + audit_paths
    if placement_path:
        protected_inputs.append(placement_path)
    if any(same_path(output, path) for path in protected_inputs):
        fail("output must not overwrite an evidence input")
    if expected_placed_count < 0:
        fail("expected placed-item count must be non-negative")
    if expected_placed_count and placement_path is None:
        fail("a placement manifest is required when placed items are expected")

    expected_atoms: Dict[str, Dict[str, Any]] = {}
    placement_record: Optional[Dict[str, Any]] = None
    if placement_path:
        placement_payload = read_json(placement_path)
        if placement_payload.get("schema_version") != "illustrator-atomic-raster-placements-v1":
            fail("placement manifest schema is unsupported")
        if placement_payload.get("scientific_pixels_modified") is not False:
            fail("placement manifest must prove scientific pixels were not modified")
        atoms = placement_payload.get("atoms")
        if not isinstance(atoms, list) or len(atoms) != expected_placed_count:
            fail("placement manifest atom count does not match expected placed-item count")
        if placement_payload.get("vector_shell_sha256") != sha256(source_svg):
            fail("placement manifest vector-shell hash does not match source SVG")
        portable_name = placement_payload.get("source_portable_svg")
        portable_sha = placement_payload.get("source_portable_svg_sha256")
        if not isinstance(portable_name, str) or not portable_name or not isinstance(portable_sha, str):
            fail("placement manifest portable SVG binding is missing")
        portable_path = resolve_file(placement_path.parent / portable_name, workspace)
        if sha256(portable_path) != portable_sha:
            fail("placement manifest portable SVG hash mismatch")
        atomic_binding = placement_payload.get("atomic_manifest")
        if not isinstance(atomic_binding, dict):
            fail("placement manifest atomic-manifest binding is missing")
        atomic_path_raw = atomic_binding.get("path")
        atomic_sha = atomic_binding.get("sha256")
        if not isinstance(atomic_path_raw, str) or not atomic_path_raw or not isinstance(atomic_sha, str):
            fail("placement manifest atomic-manifest binding is invalid")
        atomic_path = resolve_file(placement_path.parent / atomic_path_raw, workspace)
        if sha256(atomic_path) != atomic_sha:
            fail("bound atomic manifest hash mismatch")
        atomic_payload = read_json(atomic_path)
        if atomic_payload.get("scientific_pixels_modified") is not False:
            fail("atomic manifest does not prove unmodified scientific pixels")
        if atomic_payload.get("generative_cleanup_used") is not False:
            fail("atomic manifest indicates generative cleanup")
        authoritative_atoms = atomic_payload.get("atoms")
        if not isinstance(authoritative_atoms, list):
            fail("bound atomic manifest atoms are missing")
        authoritative_by_id = {
            str(record.get("id", "")): record
            for record in authoritative_atoms
            if isinstance(record, dict)
        }
        atom_records = []
        for index, atom in enumerate(atoms):
            if not isinstance(atom, dict):
                fail("placement atom must be an object")
            atom_id = str(atom.get("id", ""))
            if not atom_id or atom_id in expected_atoms:
                fail("placement atom IDs must be non-empty and unique")
            href = atom.get("href")
            expected_sha = str(atom.get("png_sha256", ""))
            if not isinstance(href, str) or not href or len(expected_sha) != 64:
                fail("placement atom path or SHA-256 is invalid: %s" % atom_id)
            atom_path = resolve_file((placement_path.parent / href).resolve(), workspace)
            if sha256(atom_path) != expected_sha:
                fail("placement atom SHA-256 mismatch: %s" % atom_id)
            authoritative = authoritative_by_id.get(atom_id)
            if not authoritative or authoritative.get("scientific_pixels_modified") is not False:
                fail("atomic manifest identity/no-modification mismatch: %s" % atom_id)
            if authoritative.get("png_sha256") != expected_sha:
                fail("atomic manifest PNG hash mismatch: %s" % atom_id)
            if authoritative.get("source_bbox_px") != atom.get("source_bbox_px"):
                fail("atomic manifest source bbox mismatch: %s" % atom_id)
            authoritative_path = resolve_file(atomic_path.parent / str(authoritative.get("path", "")), workspace)
            if not same_path(authoritative_path, atom_path):
                fail("atomic manifest file path mismatch: %s" % atom_id)
            placement = atom.get("placement_mm")
            if not isinstance(placement, dict):
                fail("placement_mm is missing: %s" % atom_id)
            normalized_placement = {
                key: finite_float(placement.get(key), "%s.%s" % (atom_id, key))
                for key in ("x", "y", "width", "height")
            }
            if normalized_placement["width"] <= 0 or normalized_placement["height"] <= 0:
                fail("placement atom dimensions must be positive: %s" % atom_id)
            expected_atoms[atom_id] = {
                "path": atom_path,
                "sha256": expected_sha,
                "placement_mm": normalized_placement,
            }
            atom_records.append({
                "id": atom_id,
                "path": relative(atom_path, output.parent),
                "sha256": expected_sha,
                "placement_mm": normalized_placement,
            })
        placement_record = {
            "path": relative(placement_path, output.parent),
            "sha256": sha256(placement_path),
            "atoms": atom_records,
            "source_portable_svg": {
                "path": relative(portable_path, output.parent),
                "sha256": portable_sha,
            },
            "atomic_manifest": {
                "path": relative(atomic_path, output.parent),
                "sha256": atomic_sha,
            },
        }

    expected_stages = ("svg_import", "ai_reopen", "editable_pdf_reopen")
    expected_documents = (source_svg, ai, pdf)
    parsed = [read_json(path) for path in audit_paths]
    counts_reference: Optional[Dict[str, int]] = None
    artboard_bounds_reference: Optional[Sequence[float]] = None
    audit_records = []
    illustrator_versions = set()
    for expected_stage, expected_document, path, audit in zip(
        expected_stages, expected_documents, audit_paths, parsed
    ):
        if audit.get("stage") != expected_stage:
            fail("stage audit mismatch: expected %s" % expected_stage)
        source_document_raw = audit.get("source_document")
        if not isinstance(source_document_raw, str) or not source_document_raw:
            fail("Illustrator stage source_document is missing: %s" % expected_stage)
        audited_document = resolve_file(Path(source_document_raw), workspace)
        if not same_path(audited_document, expected_document):
            fail("Illustrator stage source_document mismatch: %s" % expected_stage)
        warnings = audit.get("warnings")
        if not isinstance(warnings, list) or warnings:
            fail("Illustrator stage has warnings: %s" % expected_stage)
        counts = audit.get("counts")
        if not isinstance(counts, dict):
            fail("Illustrator stage counts are missing")
        normalized = {key: int(counts.get(key, -1)) for key in (
            "text_frames", "path_items", "compound_path_items", "group_items",
            "placed_items", "raster_items",
        )}
        if normalized["text_frames"] != expected_text_count:
            fail("unexpected text count in %s" % expected_stage)
        if normalized["raster_items"] != expected_raster_count:
            fail("unexpected raster count in %s" % expected_stage)
        if normalized["placed_items"] != expected_placed_count:
            fail("unexpected placed-item count in %s" % expected_stage)
        if expected_path_count is not None and normalized["path_items"] != expected_path_count:
            fail("unexpected path-item count in %s" % expected_stage)
        if expected_group_count is not None and normalized["group_items"] != expected_group_count:
            fail("unexpected group-item count in %s" % expected_stage)
        if counts_reference is None:
            counts_reference = normalized
        elif normalized != counts_reference:
            fail("Illustrator object counts changed across reopen stages")
        text_frames = audit.get("text_frames")
        if not isinstance(text_frames, list) or len(text_frames) != expected_text_count:
            fail("text frame evidence is incomplete in %s" % expected_stage)
        for frame in text_frames:
            if frame.get("font_family") != font_family:
                fail("font family mismatch in %s" % expected_stage)
            if not math.isclose(float(frame.get("size_pt")), font_size_pt, abs_tol=0.01):
                fail("font size mismatch in %s" % expected_stage)
        placed_items = audit.get("placed_items")
        if expected_placed_count:
            artboard = audit.get("active_artboard")
            if not isinstance(artboard, dict):
                fail("active artboard evidence is missing in %s" % expected_stage)
            artboard_bounds = artboard.get("bounds_pt")
            if not isinstance(artboard_bounds, list) or len(artboard_bounds) != 4:
                fail("active artboard bounds are missing in %s" % expected_stage)
            artboard_left, artboard_top, artboard_right, artboard_bottom = [
                finite_float(value, "%s.active_artboard.bounds_pt" % expected_stage)
                for value in artboard_bounds
            ]
            if artboard_right <= artboard_left or artboard_top <= artboard_bottom:
                fail("active artboard bounds are invalid in %s" % expected_stage)
            artboard_width = finite_float(
                artboard.get("width_pt"), "%s.active_artboard.width_pt" % expected_stage
            )
            artboard_height = finite_float(
                artboard.get("height_pt"), "%s.active_artboard.height_pt" % expected_stage
            )
            if not math.isclose(
                artboard_width, artboard_right - artboard_left, abs_tol=0.01
            ) or not math.isclose(
                artboard_height, artboard_top - artboard_bottom, abs_tol=0.01
            ):
                fail("active artboard dimensions disagree with bounds in %s" % expected_stage)
            normalized_artboard_bounds = (
                artboard_left,
                artboard_top,
                artboard_right,
                artboard_bottom,
            )
            if artboard_bounds_reference is None:
                artboard_bounds_reference = normalized_artboard_bounds
            elif any(
                not math.isclose(actual, reference, abs_tol=0.01)
                for actual, reference in zip(
                    normalized_artboard_bounds, artboard_bounds_reference
                )
            ):
                fail("active artboard bounds changed across reopen stages")
            if not isinstance(placed_items, list) or len(placed_items) != expected_placed_count:
                fail("placed-item evidence is incomplete in %s" % expected_stage)
            seen_items = set()
            for item in placed_items:
                if not isinstance(item, dict):
                    fail("placed-item evidence must contain objects in %s" % expected_stage)
                atom_id = str(item.get("name", ""))
                if atom_id not in expected_atoms or atom_id in seen_items:
                    fail("placed-item identity mismatch in %s" % expected_stage)
                seen_items.add(atom_id)
                file_path_raw = item.get("file_path")
                if not isinstance(file_path_raw, str) or not file_path_raw:
                    fail("placed-item linked file is missing in %s" % expected_stage)
                linked_path = resolve_file(Path(file_path_raw), workspace)
                if not same_path(linked_path, expected_atoms[atom_id]["path"]):
                    fail("placed-item linked file mismatch in %s" % expected_stage)
                actual_placement = item.get("placement_mm")
                if not isinstance(actual_placement, dict):
                    fail("placed-item placement is missing in %s" % expected_stage)
                actual_bounds = item.get("bounds_pt")
                if not isinstance(actual_bounds, list) or len(actual_bounds) != 4:
                    fail("placed-item bounds are missing in %s" % expected_stage)
                normalized_bounds = [
                    finite_float(value, "%s.bounds_pt" % atom_id) for value in actual_bounds
                ]
                for key, expected_value in expected_atoms[atom_id]["placement_mm"].items():
                    actual_value = finite_float(actual_placement.get(key), "%s.%s" % (atom_id, key))
                    if not math.isclose(actual_value, expected_value, abs_tol=0.03):
                        fail("placed-item placement mismatch in %s" % expected_stage)
                placement = expected_atoms[atom_id]["placement_mm"]
                expected_bounds = [
                    artboard_left + placement["x"] * 2.8346456693,
                    artboard_top - placement["y"] * 2.8346456693,
                    artboard_left + (placement["x"] + placement["width"]) * 2.8346456693,
                    artboard_top - (placement["y"] + placement["height"]) * 2.8346456693,
                ]
                if any(
                    not math.isclose(actual, expected, abs_tol=0.05)
                    for actual, expected in zip(normalized_bounds, expected_bounds)
                ):
                    fail("placed-item bounds mismatch in %s" % expected_stage)
        illustrator_versions.add(str(audit.get("illustrator_version", "")))
        audit_records.append({
            "stage": expected_stage,
            "path": relative(path, output.parent),
            "sha256": sha256(path),
        })
    if len(illustrator_versions) != 1 or "" in illustrator_versions:
        fail("Illustrator version evidence is inconsistent")
    structural = read_json(structural_audit)
    if structural.get("pass") is not True or structural.get("format") != "pdf":
        fail("PDF structural audit must pass")
    manifest = {
        "schema_version": "illustrator-evidence-validity-v1",
        "status": "current-svg-three-stage-roundtrip-valid",
        "illustrator_version": next(iter(illustrator_versions)),
        "source_svg": relative(source_svg, output.parent),
        "source_svg_sha256": sha256(source_svg),
        "ai": {"path": relative(ai, output.parent), "sha256": sha256(ai)},
        "editable_pdf": {
            "path": relative(pdf, output.parent),
            "sha256": sha256(pdf),
            "structural_audit": relative(structural_audit, output.parent),
            "structural_audit_sha256": sha256(structural_audit),
            "render": relative(render, output.parent),
            "render_sha256": sha256(render),
        },
        "stage_audits": audit_records,
        "verified_counts_each_stage": dict(counts_reference or {}, warnings=0),
        "verified_typography": {
            "font_family": font_family,
            "actual_size_pt": font_size_pt,
            "all_text_frames_match": True,
        },
        "verified_placed_item_count": {
            "placed_items_each_stage": expected_placed_count,
            "raster_items_each_stage": expected_raster_count,
            "note": "This aggregate count alone does not prove atom identity or byte integrity.",
        },
        "publication_ready": False,
        "remaining_blockers": list(remaining_blockers or [
            "human_200_400_percent_visual_approval_pending",
        ]),
    }
    if placement_record:
        manifest["verified_hybrid_atoms"] = {
            "status": "hash-bound-identities-links-bounds-and-placements-valid",
            "placement_manifest": placement_record,
            "verified_at_each_stage": list(expected_stages),
            "scientific_pixels_modified": False,
        }
    atomic_write(output, (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return manifest


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_svg", type=Path)
    parser.add_argument("ai", type=Path)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("svg_import_audit", type=Path)
    parser.add_argument("ai_reopen_audit", type=Path)
    parser.add_argument("pdf_reopen_audit", type=Path)
    parser.add_argument("structural_audit", type=Path)
    parser.add_argument("render", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--expected-text-count", type=int, required=True)
    parser.add_argument("--expected-raster-count", type=int, required=True)
    parser.add_argument(
        "--expected-placed-count",
        type=int,
        default=0,
        help="Expected external PlacedItem count at every Illustrator stage (default: 0).",
    )
    parser.add_argument(
        "--placement-manifest",
        type=Path,
        help="Hash-bound companion placement manifest required when expected placed count is non-zero.",
    )
    parser.add_argument("--font-family", default="Times New Roman")
    parser.add_argument("--font-size-pt", type=float, default=8.5)
    parser.add_argument("--expected-path-count", type=int)
    parser.add_argument("--expected-group-count", type=int)
    parser.add_argument(
        "--remaining-blocker",
        action="append",
        dest="remaining_blockers",
        help="Publication blocker to retain; repeat for multiple blockers.",
    )
    parser.add_argument("--force", action="store_true")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    manifest = build_manifest(
        args.source_svg, args.ai, args.pdf,
        (args.svg_import_audit, args.ai_reopen_audit, args.pdf_reopen_audit),
        args.structural_audit, args.render, args.output, args.workspace,
        args.expected_text_count, args.expected_raster_count,
        args.font_family, args.font_size_pt, force=args.force,
        expected_placed_count=args.expected_placed_count,
        placement_manifest=args.placement_manifest,
        expected_path_count=args.expected_path_count,
        expected_group_count=args.expected_group_count,
        remaining_blockers=args.remaining_blockers,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
