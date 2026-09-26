import sys
import types
import unittest
from unittest import mock
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
    def test_generated_pair_has_matching_required_lhub_taxonomy(self):
        data = {
            "title": "古民家リノベーションでLHubを活用する",
            "english_title": "Using LHub for Traditional Home Renovation",
            "description": "古民家リノベーション事業でLINEとLHubを活用し、見学予約から相談、顧客フォローまでを一貫して運用するための実務ポイントを整理します。",
            "english_description": "A practical guide to using LINE and LHub for traditional-home renovation inquiries, tour bookings, consultations, and follow-up.",
            "category": "マーケティング",
            "tags": ["LHub", "古民家", "不動産"],
            "summary": "概要です。",
            "body_markdown": "## 本文\n\n内容です。",
            "english_summary": "Summary.",
            "english_body_markdown": "## Body\n\nContent.",
        }
        jp = editorial.build_article(data, {})
        en = editorial._build_english(data)
        for article in (jp, en):
            self.assertIn('audiences:\n  - "lhub"', article)
            self.assertIn('section: "lhub-usecase"', article)
            self.assertIn('industry: "real-estate"', article)
            self.assertIn('series: "lhub-use-cases"', article)
            self.assertIn('contentType: "practical-guide"', article)

    def test_medical_lhub_taxonomy_adds_clinic_audience(self):
        audiences, industry = editorial._article_taxonomy(
            {"title": "クリニックの患者予約をLHubで改善", "tags": ["医療"]}
        )
        self.assertEqual(audiences, ["clinic", "lhub"])
        self.assertEqual(industry, "medical")

    def test_long_english_description_is_fitted_without_regeneration(self):
        value = "A practical guide to improving LINE operations for clinics and small businesses. " * 4
        fitted = editorial._fit_description(value, 50, 180, "English description")
        self.assertGreaterEqual(len(fitted), 50)
        self.assertLessEqual(len(fitted), 180)
        self.assertTrue(fitted.endswith("…"))

    def test_short_description_still_fails_quality_gate(self):
        with self.assertRaisesRegex(ValueError, "description must be 60-160"):
            editorial._fit_description("短すぎます", 60, 160, "description")

    def test_compound_request_uses_documented_minimal_shape(self):
        body = editorial._groq_request_body("groq/compound", "instructions", "payload")
        self.assertNotIn("response_format", body)
        self.assertNotIn("compound_custom", body)
        self.assertNotIn("tools", body)

    def test_gpt_oss_fallback_uses_documented_browser_search_shape(self):
        body = editorial._groq_request_body("openai/gpt-oss-120b", "instructions", "payload")
        self.assertEqual(body["tools"], [{"type": "browser_search"}])
        self.assertNotIn("response_format", body)
        self.assertIn("return a single JSON object", body["messages"][1]["content"])

    def test_provider_rejection_falls_back_once(self):
        class FakeResponse:
            def __init__(self, status_code, payload):
                self.status_code = status_code
                self._payload = payload

            def json(self):
                return self._payload

            def raise_for_status(self):
                if self.status_code >= 400:
                    raise RuntimeError(f"HTTP {self.status_code}")

        responses = [
            FakeResponse(404, {"error": {"code": "model_not_available"}}),
            FakeResponse(200, {"choices": [{"message": {"content": '{"ok": true}'}}]}),
        ]
        posted_models = []

        def fake_post(_url, **kwargs):
            posted_models.append(kwargs["json"]["model"])
            return responses.pop(0)

        timer = editorial.base.RunTimer()
        with mock.patch.dict(
            editorial.os.environ,
            {
                "GROQ_API_KEY": "test-key",
                "HDN_GROQ_MODEL": "groq/compound",
                "HDN_GROQ_FALLBACK_MODEL": "openai/gpt-oss-120b",
            },
            clear=False,
        ), mock.patch.object(editorial.requests, "post", side_effect=fake_post, create=True), mock.patch.object(
            editorial.requests, "Timeout", TimeoutError, create=True
        ):
            result = editorial.call_openai_once({}, "seed", {}, timer, False)

        self.assertEqual(result, {"ok": True})
        self.assertEqual(posted_models, ["groq/compound", "openai/gpt-oss-120b"])

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
