from __future__ import annotations

import hashlib
import json
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ATLAS = ROOT / "examples" / "capability-atlas"
SVG_NS = "{http://www.w3.org/2000/svg}"


class CapabilityAtlasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((ATLAS / "capability-manifest.json").read_text(encoding="utf-8"))

    def test_declared_coverage(self):
        self.assertEqual(self.manifest["category_count"], 8)
        self.assertEqual(self.manifest["figure_family_count"], 64)
        self.assertEqual(self.manifest["editable_svg_count"], 8)
        self.assertEqual(len(self.manifest["records"]), 8)
        self.assertTrue(all(record["card_count"] == 8 for record in self.manifest["records"]))

    def test_assets_are_hash_bound_and_raster_free(self):
        for record in self.manifest["records"]:
            svg = ATLAS / "assets" / record["svg"]
            recipe = ATLAS / "recipes" / record["recipe"]
            self.assertEqual(hashlib.sha256(svg.read_bytes()).hexdigest(), record["svg_sha256"])
            self.assertEqual(hashlib.sha256(recipe.read_bytes()).hexdigest(), record["recipe_sha256"])
            root = ET.parse(svg).getroot()
            self.assertEqual(list(root.iter(f"{SVG_NS}image")), [])
            ids = [node.attrib.get("id", "") for node in root.iter()]
            groups = [value for value in ids if value.startswith("card.") and value.count(".") == 2]
            self.assertEqual(len(groups), 8)
            self.assertGreater(len(list(root.iter(f"{SVG_NS}text"))), 15)
            self.assertGreaterEqual(record["audit"]["minimum_objects_per_card"], 15)
            self.assertEqual(len(record["audit"]["card_object_counts"]), 8)

    def test_each_family_has_a_disclosed_planning_range(self):
        self.assertIn("0 model/API calls", self.manifest["consumption_model"]["atlas_generation"])
        for record in self.manifest["records"]:
            for family in record["figure_families"]:
                estimate = family["real_task_planning_estimate"]
                self.assertIn(estimate["tier"], {"S", "M", "L", "S/M", "M/L"})
                self.assertRegex(estimate["token_range"], r"\d+.*\d+k tok")
                self.assertRegex(estimate["image_refs"], r"\d+.*img")

    def test_public_manifest_has_no_absolute_paths(self):
        payload = (ATLAS / "capability-manifest.json").read_text(encoding="utf-8")
        self.assertNotRegex(payload, r"[A-Za-z]:[\\/]")


if __name__ == "__main__":
    unittest.main()
