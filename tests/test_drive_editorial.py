import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

# The repository CI intentionally does not install Python runtime dependencies before
# unit tests. These tests only exercise pure editorial helpers, so a lightweight module
# stub is sufficient for import-time validation.
if "requests" not in sys.modules:
    sys.modules["requests"] = types.ModuleType("requests")

import generate_from_drive_editorial as editorial


class DriveEditorialTests(unittest.TestCase):
    def test_healthcare_seed_scores_above_off_brand_seed(self):
        self.assertGreater(editorial.relevance_score("クリニックのLINE患者導線改善"), 0)
        self.assertLess(editorial.relevance_score("NFTと仮想通貨の集客方法"), 0)

    def test_state_key_does_not_expose_drive_id(self):
        raw = "1PrivateDriveIdentifierABC"
        key = editorial._state_key(raw)
        self.assertNotEqual(key, raw)
        self.assertNotIn(raw, key)
        self.assertEqual(len(key), 64)

    def test_public_article_does_not_include_private_drive_reference(self):
        data = {
            "title": "患者導線を見直すときに先に確認したいこと",
            "description": "クリニックの患者導線を見直す際に、集客だけでなくLINE、問診、予約、決済、診療後の継続まで確認する実務上の視点を整理します。",
            "category": "クリニック経営",
            "tags": ["患者導線", "クリニック経営"],
            "cta": "consultation",
            "summary": "患者導線は集客だけでは完結しません。",
            "body_markdown": "## 導線は入口だけではない\n\n予約後まで確認します。",
            "faq": [],
            "references": [{"label": "HDN Japan", "url": "https://hdnjapan.com/"}],
        }
        doc = {
            "id": "1PrivateDriveIdentifierABC",
            "name": "PRIVATE SOURCE TITLE",
            "webViewLink": "https://docs.google.com/document/d/1PrivateDriveIdentifierABC/edit",
        }
        article = editorial.build_article(data, doc)
        self.assertNotIn("1PrivateDriveIdentifierABC", article)
        self.assertNotIn("docs.google.com", article)
        self.assertNotIn("PRIVATE SOURCE TITLE", article)
        self.assertIn("https://hdnjapan.com/", article)


if __name__ == "__main__":
    unittest.main()
