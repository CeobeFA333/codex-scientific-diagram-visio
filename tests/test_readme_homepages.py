from __future__ import annotations

import re
import unittest
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
README_PATHS = (ROOT / "README.md", ROOT / "README.zh-CN.md")
LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


class ReadmeHomepageTests(unittest.TestCase):
    def test_relative_links_exist(self) -> None:
        for readme in README_PATHS:
            text = readme.read_text(encoding="utf-8")
            for raw_target in LINK_RE.findall(text):
                target = raw_target.strip("<>")
                if target.startswith(("#", "http://", "https://", "mailto:", "codex:")):
                    continue
                relative = unquote(target.split("#", 1)[0].split("?", 1)[0])
                with self.subTest(readme=readme.name, target=target):
                    self.assertTrue((readme.parent / relative).exists())

    def test_bilingual_structure_stays_in_sync(self) -> None:
        english, chinese = (
            path.read_text(encoding="utf-8") for path in README_PATHS
        )
        for prefix in ("## ", "### "):
            self.assertEqual(
                len(re.findall(rf"^{re.escape(prefix)}", english, re.MULTILINE)),
                len(re.findall(rf"^{re.escape(prefix)}", chinese, re.MULTILINE)),
            )
        for text in (english, chinese):
            self.assertEqual(text.count("<details>"), text.count("</details>"))
            self.assertEqual(text.count("<summary>"), text.count("</summary>"))


if __name__ == "__main__":
    unittest.main()
