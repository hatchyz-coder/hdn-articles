import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import lhub_daily_preflight as preflight


class LHubDailyPreflightTests(unittest.TestCase):
    def test_detects_published_lhub_article_without_dependencies(self):
        with tempfile.TemporaryDirectory() as tmp:
            article_dir = Path(tmp)
            (article_dir / "today.md").write_text(
                "---\npublishedAt: 2026-09-28\ndraft: false\nsection: lhub-usecase\n---\nbody\n",
                encoding="utf-8",
            )
            self.assertEqual(
                preflight.published_lhub_slugs_for_day(article_dir, "2026-09-28"),
                ["today"],
            )

    def test_ignores_drafts_and_non_lhub_articles(self):
        with tempfile.TemporaryDirectory() as tmp:
            article_dir = Path(tmp)
            (article_dir / "draft.md").write_text(
                "---\npublishedAt: 2026-09-28\ndraft: true\nsection: lhub-usecase\n---\nbody\n",
                encoding="utf-8",
            )
            (article_dir / "other.md").write_text(
                "---\npublishedAt: 2026-09-28\ndraft: false\nsection: world-frictions\n---\nbody\n",
                encoding="utf-8",
            )
            self.assertEqual(preflight.published_lhub_slugs_for_day(article_dir, "2026-09-28"), [])

    def test_preflight_main_stops_before_full_pipeline_when_published(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            today = preflight.datetime.now(preflight.JST).date().isoformat()
            (root / "today.md").write_text(
                f"---\npublishedAt: {today}\ndraft: false\nsection: lhub-usecase\n---\nbody\n",
                encoding="utf-8",
            )
            outputs = {}
            def capture(key, value):
                outputs[key] = value
            with mock.patch.object(preflight, "ARTICLE_DIR", root), \
                 mock.patch.object(preflight, "emit", side_effect=capture):
                self.assertEqual(preflight.main(), 0)
            self.assertEqual(outputs["published"], "true")
            self.assertEqual(outputs["reason"], "already_published_today")
            self.assertEqual(outputs["published_slug"], "today")


if __name__ == "__main__":
    unittest.main()
