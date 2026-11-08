import shutil
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import prepare_lhub_backfill as backfill
import audit_lhub_daily as audit
import lhub_daily_preflight as preflight


class BackfillRecoveryTests(unittest.TestCase):
    def fixture(self, root):
        target = root / "fallback" / "lhub"
        target.mkdir(parents=True)
        for source in backfill.MANIFEST.values():
            shutil.copy2(ROOT / "fallback" / "lhub" / source, target / source)

    def test_prepare_only_previews_without_a_write_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            result = backfill.prepare(root, date(2026, 11, 8))
            self.assertEqual(len(result), 7)
            self.assertFalse((root / "src/content/articles").exists())

    def test_backfill_keeps_actual_release_date_and_historic_due_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            result = backfill.prepare(root, date(2026, 11, 8), preview=False)
            self.assertEqual(len(result), 7)
            for item in result:
                jp = (root / "src/content/articles" / (item["slug"] + ".md")).read_text(encoding="utf-8")
                en = (root / "src/content/articles-en" / (item["slug"] + ".md")).read_text(encoding="utf-8")
                self.assertIn("publishedAt: 2026-11-08", jp)
                self.assertIn("publishedAt: 2026-11-08", en)
                self.assertIn("backfillFor: " + item["original_due_date"], jp)
                self.assertIn("backfillFor: " + item["original_due_date"], en)
                self.assertNotIn("publishedAt: " + item["original_due_date"], jp)
            self.assertEqual(preflight.published_lhub_slugs_for_day(root / "src/content/articles", "2026-11-08"), [])
            audit_result = audit.audit(root, date(2026, 10, 31), date(2026, 11, 6))
            self.assertEqual(len(audit_result["backfilled_days"]), 7)
            self.assertEqual(audit_result["uncompensated_days"], [])
            self.assertEqual(len(audit_result["missing_days"]), 7)

    def test_backfill_refuses_a_duplicate_slug(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            slug = "lhub-reserve-clinic-consent-explanation-timing-202611"
            article_dir = root / "src/content/articles"
            article_dir.mkdir(parents=True)
            (article_dir / (slug + ".md")).write_text("existing", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                backfill.prepare(root, date(2026, 11, 8), preview=False)


if __name__ == "__main__":
    unittest.main()
