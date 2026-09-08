#!/usr/bin/env python3
"""Build a deterministic, source-only release archive for this skill."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import zipfile
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple


SCHEMA_VERSION = "reconstruct-paper-figures-release-v1"
MANIFEST_SCHEMA_VERSION = "reconstruct-paper-figures-archive-v1"
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$")
ROOT_FILES = ("SKILL.md", "VERSION", "LICENSE", "release-profile.json")
ALLOWED_SUFFIXES = {".md", ".json", ".py", ".jsx", ".mjs", ".yaml", ".yml"}


class ReleaseError(ValueError):
    """Raised when release inputs violate the source-only contract."""


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def is_within(path: Path, directory: Path) -> bool:
    try:
        path.relative_to(directory)
    except ValueError:
        return False
    return True


def relative_file(skill_root: Path, raw: object, field: str) -> Path:
    if not isinstance(raw, str) or not raw.strip():
        raise ReleaseError("%s must contain non-empty relative file paths" % field)
    candidate = Path(raw)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ReleaseError("%s path escapes the skill: %s" % (field, raw))
    resolved = (skill_root / candidate).resolve()
    if not is_within(resolved, skill_root) or not resolved.is_file():
        raise ReleaseError("%s file is missing or outside the skill: %s" % (field, raw))
    return resolved


def validate_declared_files(skill_root: Path, profile: Dict[str, object]) -> None:
    relative_file(skill_root, profile.get("primary_entrypoint"), "primary_entrypoint")
    for field in ("entrypoints", "required_references"):
        values = profile.get(field)
        if not isinstance(values, list) or not values:
            raise ReleaseError("%s must be a non-empty list" % field)
        for value in values:
            relative_file(skill_root, value, field)


def validate_package_roots(skill_root: Path, profile: Dict[str, object]) -> None:
    roots = profile.get("package_roots")
    if not isinstance(roots, list) or not roots:
        raise ReleaseError("package_roots must be a non-empty list")
    for raw in roots:
        candidate = Path(str(raw))
        if not isinstance(raw, str) or candidate.is_absolute() or ".." in candidate.parts:
            raise ReleaseError("package_roots must contain safe relative directories")
        directory = (skill_root / candidate).resolve()
        if not is_within(directory, skill_root) or not directory.is_dir():
            raise ReleaseError("package root is missing or outside the skill: %s" % raw)


def validate_github_profile(profile: Dict[str, object]) -> None:
    github = profile.get("github")
    if not isinstance(github, dict) or not isinstance(github.get("release_blockers"), list):
        raise ReleaseError("github.release_blockers must be declared")


def load_profile(skill_root: Path) -> Dict[str, object]:
    profile_path = skill_root / "release-profile.json"
    try:
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReleaseError("Cannot read release profile: %s" % exc) from exc
    if profile.get("schema_version") != SCHEMA_VERSION:
        raise ReleaseError("release profile schema_version must be %s" % SCHEMA_VERSION)
    if profile.get("name") != skill_root.name:
        raise ReleaseError("release profile name must match the skill directory")
    version = str(profile.get("version", ""))
    if not SEMVER_RE.fullmatch(version):
        raise ReleaseError("release profile version must be semantic-version compatible")
    version_file = (skill_root / "VERSION").read_text(encoding="utf-8").strip()
    if version_file != version:
        raise ReleaseError("VERSION and release-profile.json disagree")
    validate_declared_files(skill_root, profile)
    validate_package_roots(skill_root, profile)
    validate_github_profile(profile)
    return profile


def iter_packaged_root_files(skill_root: Path, roots: Sequence[object]) -> Iterable[Path]:
    for raw_root in roots:
        root = skill_root / str(raw_root)
        for path in root.rglob("*"):
            if not path.is_file() or path.is_symlink():
                continue
            relative = path.relative_to(skill_root)
            if "__pycache__" in relative.parts or path.suffix.lower() in {".pyc", ".pyo"}:
                continue
            if path.suffix.lower() not in ALLOWED_SUFFIXES:
                raise ReleaseError("unsupported file type in release roots: %s" % relative)
            yield path


def collect_files(skill_root: Path, profile: Dict[str, object]) -> List[Path]:
    files = []
    for name in ROOT_FILES:
        path = skill_root / name
        if not path.is_file():
            raise ReleaseError("required release file is missing: %s" % name)
        files.append(path)
    files.extend(iter_packaged_root_files(skill_root, profile["package_roots"]))
    unique = sorted(set(files), key=lambda path: path.relative_to(skill_root).as_posix())
    if not unique:
        raise ReleaseError("release archive would be empty")
    return unique


def validate_sources(skill_root: Path, files: Sequence[Path]) -> None:
    for path in files:
        relative = path.relative_to(skill_root).as_posix()
        if path.suffix.lower() == ".py":
            try:
                ast.parse(path.read_text(encoding="utf-8"), filename=relative)
            except (OSError, SyntaxError) as exc:
                raise ReleaseError("invalid Python source %s: %s" % (relative, exc)) from exc
        elif path.suffix.lower() == ".json":
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ReleaseError("invalid JSON source %s: %s" % (relative, exc)) from exc


def file_records(skill_root: Path, files: Iterable[Path]) -> List[Dict[str, object]]:
    return [
        {
            "path": path.relative_to(skill_root).as_posix(),
            "sha256": sha256_file(path),
            "size_bytes": path.stat().st_size,
        }
        for path in files
    ]


def zip_entry(name: str, payload: bytes) -> Tuple[zipfile.ZipInfo, bytes]:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    info.create_system = 3
    return info, payload


def write_archive(
    skill_root: Path,
    output: Path,
    profile: Dict[str, object],
    files: Sequence[Path],
) -> Dict[str, object]:
    records = file_records(skill_root, files)
    github = profile["github"]
    blockers = list(github["release_blockers"])
    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "name": profile["name"],
        "version": profile["version"],
        "maturity": profile["maturity"],
        "source_only": True,
        "github_upload_ready": not blockers,
        "release_blockers": blockers,
        "files": records,
    }
    prefix = "%s/" % profile["name"]
    manifest_payload = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    temporary = output.with_name(output.name + ".tmp")
    if temporary.exists():
        raise FileExistsError("Refusing stale temporary archive: %s" % temporary)
    try:
        with zipfile.ZipFile(temporary, "w") as archive:
            info, payload = zip_entry(prefix + "RELEASE-MANIFEST.json", manifest_payload)
            archive.writestr(info, payload)
            for path in files:
                name = prefix + path.relative_to(skill_root).as_posix()
                info, payload = zip_entry(name, path.read_bytes())
                archive.writestr(info, payload)
        os.replace(str(temporary), str(output))
    finally:
        if temporary.exists():
            temporary.unlink()
    return manifest


def build_release(
    skill_root: Path,
    output: Path,
    workspace: Path,
    force: bool = False,
) -> Dict[str, object]:
    workspace = workspace.resolve()
    if not skill_root.is_absolute():
        skill_root = workspace / skill_root
    if not output.is_absolute():
        output = workspace / output
    skill_root = skill_root.resolve()
    output = output.resolve()
    if not skill_root.is_dir() or not is_within(skill_root, workspace):
        raise ReleaseError("skill root must be an existing directory inside the workspace")
    if output.suffix.lower() != ".zip" or not is_within(output, workspace):
        raise ReleaseError("release output must be a .zip inside the workspace")
    if is_within(output, skill_root):
        raise ReleaseError("release output must remain outside the packaged skill")
    audit_path = output.with_suffix(".audit.json")
    existing = [path for path in (output, audit_path) if path.exists()]
    if existing and not force:
        raise FileExistsError(
            "Refusing to overwrite release output(s): %s"
            % ", ".join(str(path) for path in existing)
        )
    profile = load_profile(skill_root)
    files = collect_files(skill_root, profile)
    validate_sources(skill_root, files)
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest = write_archive(skill_root, output, profile, files)
    audit = {
        "schema_version": "reconstruct-paper-figures-release-audit-v1",
        "pass": True,
        "name": profile["name"],
        "version": profile["version"],
        "archive": output.name,
        "archive_sha256": sha256_file(output),
        "archive_size_bytes": output.stat().st_size,
        "packaged_file_count": len(files),
        "source_only": True,
        "github_upload_ready": manifest["github_upload_ready"],
        "release_blockers": manifest["release_blockers"],
        "excluded_workspace_assets": profile["github"]["excluded_from_skill_archive"],
    }
    payload = (json.dumps(audit, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    temporary = audit_path.with_name(audit_path.name + ".tmp")
    if temporary.exists():
        raise FileExistsError("Refusing stale temporary audit: %s" % temporary)
    try:
        temporary.write_bytes(payload)
        os.replace(str(temporary), str(audit_path))
    finally:
        if temporary.exists():
            temporary.unlink()
    return audit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a deterministic source-only reconstruct-paper-figures release archive."
    )
    parser.add_argument("output", type=Path, help="Destination .zip inside the workspace")
    parser.add_argument(
        "--skill-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Skill directory; defaults to the parent of this script directory",
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path.cwd(),
        help="Boundary that must contain the skill and output",
    )
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    audit = build_release(args.skill_root, args.output, args.workspace, force=args.force)
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
