"""Module-local smoke tests; repository CI runs the fuller root-level suite."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


MODULE = Path(__file__).resolve().parents[1]


class ManifestSmokeTest(unittest.TestCase):
    def test_manifest_declares_all_categories_and_families(self):
        manifest = json.loads(
            (MODULE / "capability-manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["category_count"], 8)
        self.assertEqual(manifest["figure_family_count"], 64)
        self.assertIn("0 model/API calls", manifest["consumption_model"]["atlas_generation"])


if __name__ == "__main__":
    unittest.main()
