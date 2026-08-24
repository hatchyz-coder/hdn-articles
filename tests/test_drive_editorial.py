import sys
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

if "requests" not in sys.modules:
    requests_stub = types.ModuleType("requests")
    requests_stub.Timeout = TimeoutError
    sys.modules["requests"] = requests_stub

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
        self.assertEqual([doc["name"] for doc in ordered], ["LH6_記事1_最初", "LH6_記事2_先", "LH10_記事1_後", "番号なし"])

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

    def test_old_confidential_skip_is_requeued_after_processor_upgrade(self):
        doc = {"id": "doc-1", "name": "LH6_記事1", "modifiedTime": "2026-08-20T00:00:00Z"}
        state = {"documents": {editorial._state_key("doc-1"): {"modifiedTime": doc["modifiedTime"], "status": "skipped_confidential", "retry_count": 0}}}
        self.assertTrue(editorial.is_unprocessed_or_updated(state, doc))

    def test_current_generated_item_is_not_requeued(self):
        doc = {"id": "doc-2", "name": "LH6_記事2", "modifiedTime": "2026-08-20T00:00:00Z"}
        state = {"documents": {editorial._state_key("doc-2"): {"modifiedTime": doc["modifiedTime"], "status": "generated", "retry_count": 0, "processorVersion": editorial.PROCESSOR_VERSION}}}
        self.assertFalse(editorial.is_unprocessed_or_updated(state, doc))

    def test_published_seed_is_not_requeued_after_drive_edit(self):
        doc = {"id": "published-doc", "name": "LH6_記事3", "modifiedTime": "2026-08-24T00:00:00Z"}
        state = {"documents": {editorial._state_key(doc["id"]): {"modifiedTime": "2026-08-20T00:00:00Z", "status": "published", "processorVersion": editorial.PROCESSOR_VERSION}}}
        self.assertFalse(editorial.is_unprocessed_or_updated(state, doc))

    def test_seed_sanitizer_redacts_direct_identifiers_before_ai(self):
        text = "連絡先 test@example.com 電話 090-1234-5678 APIキー: secret-value"
        sanitized, flags = editorial.sanitize_seed_text(text)
        self.assertNotIn("test@example.com", sanitized)
        self.assertNotIn("090-1234-5678", sanitized)
        self.assertNotIn("secret-value", sanitized)
        self.assertTrue(flags)

    def test_public_privacy_check_does_not_block_generic_pricing(self):
        data = {"body_markdown": "公開料金として月額5,000円のサービスを比較する。"}
        self.assertEqual(editorial.validate_sanitized_output(data), [])

    def test_public_privacy_check_sanitizes_email_and_secret_without_veto(self):
        email_data = {"body_markdown": "連絡先は person@example.com"}
        secret_data = {"body_markdown": "APIキー: abc123"}
        self.assertEqual(editorial.validate_sanitized_output(email_data), [])
        self.assertEqual(editorial.validate_sanitized_output(secret_data), [])
        self.assertNotIn("person@example.com", email_data["body_markdown"])
        self.assertNotIn("abc123", secret_data["body_markdown"])

    def test_unique_slug_never_returns_existing_pair_path(self):
        original_jp = editorial.impl.base.ARTICLE_DIR
        original_en = editorial.impl.EN_ARTICLE_DIR
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            jp = root / "jp"
            en = root / "en"
            jp.mkdir()
            en.mkdir()
            editorial.impl.base.ARTICLE_DIR = jp
            editorial.impl.EN_ARTICLE_DIR = en
            try:
                doc_id = "same-doc"
                base_slug = "repeated-title"
                suffix = __import__('hashlib').sha256(doc_id.encode('utf-8')).hexdigest()[:8]
                (jp / f"{base_slug}.md").write_text("existing", encoding="utf-8")
                (en / f"{base_slug}-{suffix}.md").write_text("existing", encoding="utf-8")
                slug = editorial.unique_slug(base_slug, doc_id)
                self.assertNotEqual(slug, base_slug)
                self.assertNotEqual(slug, f"{base_slug}-{suffix}")
                self.assertFalse((jp / f"{slug}.md").exists())
                self.assertFalse((en / f"{slug}.md").exists())
            finally:
                editorial.impl.base.ARTICLE_DIR = original_jp
                editorial.impl.EN_ARTICLE_DIR = original_en

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
        doc = {"id": "1PrivateDriveIdentifierABC", "name": "PRIVATE SOURCE TITLE", "webViewLink": "https://docs.google.com/document/d/1PrivateDriveIdentifierABC/edit"}
        article = editorial.build_article(data, doc)
        self.assertNotIn("1PrivateDriveIdentifierABC", article)
        self.assertNotIn("docs.google.com", article)
        self.assertNotIn("PRIVATE SOURCE TITLE", article)
        self.assertIn("https://hdnjapan.com/", article)


if __name__ == "__main__":
    unittest.main()
