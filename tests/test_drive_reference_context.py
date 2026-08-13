import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from drive_reference_context import _rank_documents, load_reference_context, sanitize_private_context


class DriveReferenceContextTests(unittest.TestCase):
    def test_sanitizes_contact_amount_secret_and_drive_identifiers(self):
        raw = (
            "担当 test@example.com 03-1234-5678 月額: 100,000円 "
            "APIキー: supersecret123 https://drive.google.com/file/d/123/view "
            "https://docs.google.com/document/d/1AbCdEfGhIjKlMnOpQrStUvWxYz/edit"
        )
        safe = sanitize_private_context(raw)
        self.assertNotIn("test@example.com", safe)
        self.assertNotIn("03-1234-5678", safe)
        self.assertNotIn("100,000円", safe)
        self.assertNotIn("supersecret123", safe)
        self.assertNotIn("drive.google.com", safe)
        self.assertNotIn("docs.google.com", safe)

    def test_lhub_archive_ranking_prefers_relevant_lhub_title(self):
        items = [
            {"name": "一般的な業務資料", "modifiedTime": "2026-08-13T00:00:00Z"},
            {"name": "LHub オンライン診療 予約 決済", "modifiedTime": "2026-08-12T00:00:00Z"},
            {"name": "LHub 飲食店 会員制", "modifiedTime": "2026-08-13T00:00:00Z"},
        ]
        ranked = _rank_documents(items, "オンライン診療の予約と決済", "lhub_archive")
        self.assertEqual(ranked[0]["name"], "LHub オンライン診療 予約 決済")

    def test_missing_environment_is_safe_noop(self):
        keys = [
            "GOOGLE_SERVICE_ACCOUNT_JSON",
            "GOOGLE_DRIVE_INTERNAL_REFERENCE_FOLDER_ID",
            "GOOGLE_DRIVE_LHUB_ARCHIVE_FOLDER_ID",
        ]
        old = {key: os.environ.pop(key, None) for key in keys}
        try:
            context = load_reference_context("医療DX")
            self.assertFalse(context["available"])
            self.assertEqual(context["internal_operations"], [])
            self.assertEqual(context["lhub_archive"], [])
        finally:
            for key, value in old.items():
                if value is not None:
                    os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
