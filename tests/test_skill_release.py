from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/reconstruct-paper-figures/scripts/build_skill_release.py"
SPEC = importlib.util.spec_from_file_location("build_skill_release", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SkillReleaseTests(unittest.TestCase):
    def make_skill(self, workspace: Path) -> Path:
        skill = workspace / "reconstruct-paper-figures"
        (skill / "agents").mkdir(parents=True)
        (skill / "scripts" / "__pycache__").mkdir(parents=True)
        (skill / "references").mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            "---\nname: reconstruct-paper-figures\n"
            "description: Reconstruct paper figures.\n---\n",
            encoding="utf-8",
        )
        (skill / "VERSION").write_text("0.1.0\n", encoding="utf-8")
        (skill / "LICENSE").write_text("MIT License\n", encoding="utf-8")
        (skill / "agents" / "openai.yaml").write_text(
            """interface:
  display_name: test
""",
            encoding="utf-8",
        )
        (skill / "scripts" / "entry.py").write_text(
            "def main():\n    return 0\n", encoding="utf-8"
        )
        (skill / "scripts" / "__pycache__" / "entry.pyc").write_bytes(b"bytecode")
        (skill / "references" / "contract.md").write_text("# Contract\n", encoding="utf-8")
        profile = {
            "schema_version": "reconstruct-paper-figures-release-v1",
            "name": "reconstruct-paper-figures",
            "version": "0.1.0",
            "maturity": "stable",
            "primary_entrypoint": "SKILL.md",
            "entrypoints": ["scripts/entry.py"],
            "required_references": ["references/contract.md"],
            "package_roots": ["agents", "scripts", "references"],
            "github": {
                "release_blockers": ["fixture_blocker"],
                "excluded_from_skill_archive": ["paper PDFs", "Python bytecode"],
            },
        }
        (skill / "release-profile.json").write_text(
            json.dumps(profile), encoding="utf-8"
        )
        return skill

    def test_build_is_deterministic_source_only_and_hash_audited(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            skill = self.make_skill(workspace)
            first = MODULE.build_release(skill, workspace / "first.zip", workspace)
            second = MODULE.build_release(skill, workspace / "second.zip", workspace)
            self.assertEqual(first["archive_sha256"], second["archive_sha256"])
            self.assertFalse(first["github_upload_ready"])
            self.assertEqual(["fixture_blocker"], first["release_blockers"])
            with zipfile.ZipFile(workspace / "first.zip") as archive:
                names = archive.namelist()
                self.assertIn("reconstruct-paper-figures/LICENSE", names)
                self.assertIn("reconstruct-paper-figures/scripts/entry.py", names)
                self.assertFalse(any("__pycache__" in name for name in names))
                self.assertFalse(any(name.endswith(".pyc") for name in names))

    def test_refuses_overwrite_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            skill = self.make_skill(workspace)
            output = workspace / "release.zip"
            MODULE.build_release(skill, output, workspace)
            before = output.read_bytes()
            with self.assertRaises(FileExistsError):
                MODULE.build_release(skill, output, workspace)
            self.assertEqual(before, output.read_bytes())

    def test_rejects_version_mismatch_before_output(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            skill = self.make_skill(workspace)
            (skill / "VERSION").write_text("0.2.0\n", encoding="utf-8")
            output = workspace / "release.zip"
            with self.assertRaisesRegex(MODULE.ReleaseError, "disagree"):
                MODULE.build_release(skill, output, workspace)
            self.assertFalse(output.exists())

    def test_rejects_output_outside_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as raw, tempfile.TemporaryDirectory() as outside:
            workspace = Path(raw)
            skill = self.make_skill(workspace)
            output = Path(outside) / "release.zip"
            with self.assertRaisesRegex(MODULE.ReleaseError, "inside the workspace"):
                MODULE.build_release(skill, output, workspace)

    def test_actual_release_is_public_mit_and_source_only(self) -> None:
        skill = (ROOT / "skills/reconstruct-paper-figures").resolve()
        profile = MODULE.load_profile(skill)
        files = MODULE.collect_files(skill, profile)
        MODULE.validate_sources(skill, files)
        self.assertEqual("0.1.0", profile["version"])
        self.assertEqual("MIT", profile["license"])
        self.assertTrue(profile["github"]["github_upload_ready"])
        self.assertEqual([], profile["github"]["release_blockers"])
        self.assertIn(skill / "LICENSE", files)
        self.assertFalse(any("__pycache__" in path.parts for path in files))


if __name__ == "__main__":
    unittest.main()
