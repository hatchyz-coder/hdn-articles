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
    def test_healthcare_seed_scores_above_off_brand_seed_for_diagnostics_only(self):
        self.assertGreater(editorial.relevance_score("クリニックのLINE患者導線改善"), 0)
        self.assertLess(editorial.relevance_score("NFTと仮想通貨の集客方法"), 0)

    def test_explicit_published_marker_is_detected(self):
        self.assertTrue(editorial.is_marked_published("LH5_記事1_LINE活用 済 のコピー"))
        self.assertTrue(editorial.is_marked_published("LH9_記事7_クラフトビール（202511済） のコピー"))

    def test_payment_word_is_not_mistaken_for_published_marker(self):
        self.assertFalse(editorial.is_marked_published("LH5_記事2_LINE × 定期販売・会費管理・決済"))
        self.assertFalse(editorial.is_marked_published("LH7_記事1_予約・決済・処方のスマート導線"))

    def test_queue_orders_lh_then_article_number(self):
        docs = [
            {"name": "LH10_記事1_後", "modifiedTime": "2026-01-01T00:00:00Z"},
            {"name": "LH6_記事2_先", "modifiedTime": "2026-01-01T00:00:00Z"},
            {"name": "LH6_記事1_最初", "modifiedTime": "2026-01-01T00:00:00Z"},
            {"name": "番号なし", "modifiedTime": "2025-01-01T00:00:00Z"},
        ]
        ordered = sorted(docs, key=editorial.queue_sort_key)
        self.assertEqual(
            [doc["name"] for doc in ordered],
            ["LH6_記事1_最初", "LH6_記事2_先", "LH10_記事1_後", "番号なし"],
        )

    def test_non_lh_drafts_fall_back_oldest_first(self):
        docs = [
            {"name": "newer", "modifiedTime": "2026-02-01T00:00:00Z"},
            {"name": "older", "modifiedTime": "2026-01-01T00:00:00Z"},
        ]
        ordered = sorted(docs, key=editorial.queue_sort_key)
        self.assertEqual([doc["name"] for doc in ordered], ["older", "newer"])

    def test_approved_folder_fingerprint_fails_closed(self):
        editorial._verify_approved_folder("1R8K22La-iytMBhwhGTj8qhHyl3Zd9FXz")
        with self.assertRaises(RuntimeError):
            editorial._verify_approved_folder("wrong-folder")

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

    def test_prompt_requires_empty_flags_after_successful_sanitization(self):
        prompt = editorial.PROMPT_PATH.read_text(encoding="utf-8")
        self.assertIn("EMPTY `confidentiality_flags` array", prompt)
        self.assertIn("residual privacy/confidentiality blockers", prompt)

    def test_deterministic_seed_prefilter_still_blocks_direct_private_data(self):
        flags = editorial.base.confidentiality_flags("seed", "連絡先 test.person@example.com")
        self.assertIn("email_address", flags)


if __name__ == "__main__":
    unittest.main()
