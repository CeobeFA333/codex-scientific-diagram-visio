#!/usr/bin/env python3
"""Validate the public release structure without third-party dependencies."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def parse_frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        fail(f"missing YAML frontmatter: {path}")
    end = text.find("\n---\n", 4)
    if end < 0:
        fail(f"unterminated YAML frontmatter: {path}")
    values: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if ":" not in line:
            fail(f"unsupported frontmatter line in {path}: {line}")
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip()
    if set(values) != {"name", "description"}:
        fail(f"frontmatter must contain only name/description: {path}")
    if not NAME_RE.fullmatch(values["name"]):
        fail(f"invalid skill name: {values['name']}")
    if not values["description"]:
        fail(f"empty skill description: {path}")
    return values


def validate_paper_demo() -> None:
    assets = ROOT / "examples" / "paper-figure-reconstruction-demo" / "assets"
    manifest_path = assets / "demo-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("plugin_version") != "1.3.1":
        fail("paper demo manifest must target plugin version 1.3.1")
    if manifest.get("screen_recording") is not False:
        fail("paper demo must identify itself as evidence-driven, not a screen recording")
    for record in manifest.get("files", []):
        path = assets / record.get("path", "")
        if not path.is_file():
            fail(f"paper demo asset is missing: {path}")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != record.get("sha256"):
            fail(f"paper demo asset hash mismatch: {path.name}")
    gif_path = assets / "paper-figure-reconstruction-demo.gif"
    if gif_path.read_bytes()[:6] not in {b"GIF87a", b"GIF89a"}:
        fail("paper demo GIF has an invalid signature")
    mp4_path = assets / "paper-figure-reconstruction-demo.mp4"
    if b"ftyp" not in mp4_path.read_bytes()[:32]:
        fail("paper demo MP4 has an invalid signature")
    evidence = json.loads((assets / "simpli-figure4-evidence.json").read_text(encoding="utf-8"))
    expected_counts = {
        "text_frames": 102,
        "path_items": 4466,
        "group_items": 15,
        "placed_items": 3,
        "raster_items": 0,
        "warnings": 0,
    }
    counts = evidence.get("verified_counts_each_stage", {})
    if any(counts.get(key) != value for key, value in expected_counts.items()):
        fail("paper demo Illustrator evidence counts changed")
    if evidence.get("publication_ready") is not False:
        fail("paper demo must retain the blocked publication status")


def skill_hashes(root: Path) -> dict[Path, str]:
    return {
        path.relative_to(root): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.relative_to(root).parts
        and path.suffix.lower() not in {".pyc", ".pyo"}
    }


def main() -> int:
    manifest_path = ROOT / ".codex-plugin" / "plugin.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("name") != "codex-scientific-diagram-visio":
        fail("unexpected plugin name")
    if manifest.get("version") != "1.3.1":
        fail("release manifest must be version 1.3.1")

    marketplace_path = ROOT / ".agents" / "plugins" / "marketplace.json"
    marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))
    entries = marketplace.get("plugins", [])
    if len(entries) != 1 or entries[0].get("name") != manifest["name"]:
        fail("marketplace must expose exactly the release plugin")
    plugin_copy = ROOT / "plugins" / manifest["name"]
    copied_manifest = json.loads(
        (plugin_copy / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    if copied_manifest != manifest:
        fail("marketplace plugin manifest is out of sync")

    expected = {
        "scientific-model-diagram-prompting",
        "scientific-model-diagram-visio",
        "reconstruct-paper-figures",
    }
    found: set[str] = set()
    for path in sorted((ROOT / "skills").glob("*/SKILL.md")):
        metadata = parse_frontmatter(path)
        if path.parent.name != metadata["name"]:
            fail(f"folder/frontmatter name mismatch: {path}")
        found.add(metadata["name"])
    if found != expected:
        fail(f"unexpected skill set: {sorted(found)}")

    for skill_name in expected:
        canonical = ROOT / "skills" / skill_name
        copied = plugin_copy / "skills" / skill_name
        canonical_files = skill_hashes(canonical)
        copied_files = skill_hashes(copied)
        if canonical_files != copied_files:
            fail(f"marketplace copy is out of sync: {skill_name}")

    reconstruction_profile = json.loads(
        (ROOT / "skills" / "reconstruct-paper-figures" / "release-profile.json").read_text(encoding="utf-8")
    )
    if reconstruction_profile.get("license") != "MIT":
        fail("reconstruct-paper-figures must declare MIT")
    if reconstruction_profile.get("github", {}).get("github_upload_ready") is not True:
        fail("reconstruct-paper-figures is not marked ready for GitHub")
    if not (ROOT / "skills" / "reconstruct-paper-figures" / "LICENSE").is_file():
        fail("reconstruct-paper-figures standalone MIT license is missing")

    validate_paper_demo()

    forbidden = re.compile(
        r"(?:[A-Za-z]:\\|/Users/|/home/|AppData|pythonProject|ResRMTN|OPENAI_API_KEY\s*=)",
        re.IGNORECASE,
    )
    scan_suffixes = {".md", ".yaml", ".yml", ".json", ".py", ".ps1", ".txt"}
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in scan_suffixes:
            continue
        if any(part in {".git", "build", "__pycache__"} for part in path.parts):
            continue
        if path.resolve() == Path(__file__).resolve():
            continue
        text = path.read_text(encoding="utf-8")
        match = forbidden.search(text)
        if match:
            fail(f"possible private path or secret pattern in {path}: {match.group(0)}")

    print("Release validation passed.")
    print(f"Plugin: {manifest['name']} v{manifest['version']}")
    print(f"Skills: {', '.join(sorted(found))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
