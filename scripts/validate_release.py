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


def main() -> int:
    manifest_path = ROOT / ".codex-plugin" / "plugin.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("name") != "codex-scientific-diagram-visio":
        fail("unexpected plugin name")
    if manifest.get("version") != "1.2.0":
        fail("release manifest must be version 1.2.0")

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
        canonical_files = {
            path.relative_to(canonical): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in canonical.rglob("*")
            if path.is_file()
        }
        copied_files = {
            path.relative_to(copied): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in copied.rglob("*")
            if path.is_file()
        }
        if canonical_files != copied_files:
            fail(f"marketplace copy is out of sync: {skill_name}")

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
