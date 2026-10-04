import importlib.util
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import lhub_daily_guarantee as guarantee
from publication_fact_gate import evaluate


class LHubDailyGuaranteeTests(unittest.TestCase):
    def test_detects_existing_lhub_publication_for_day(self):
        with tempfile.TemporaryDirectory() as tmp:
            article_dir = Path(tmp)
            (article_dir / "today.md").write_text(
                "---\ntitle: Today\ndescription: " + "a" * 60 +
                "\npublishedAt: 2026-09-27\ndraft: false\nsection: lhub-usecase\n---\nbody\n",
                encoding="utf-8",
            )
            self.assertEqual(
                guarantee.published_lhub_slugs_for_day(article_dir, "2026-09-27"),
                ["today"],
            )

    def test_reserve_pool_is_valid_fact_gated_and_replenished(self):
        paths = sorted((ROOT / "fallback" / "lhub").glob("*.json"))
        self.assertGreaterEqual(len(paths), 30)
        for path in paths:
            data = json.loads(path.read_text(encoding="utf-8"))
            jp, en = guarantee.validate_reserve(data, "2026-09-27")
            self.assertTrue(evaluate(jp)["publication_fact_gate"], path.name)
            self.assertTrue(evaluate(en)["publication_fact_gate"], path.name)
            self.assertGreaterEqual(guarantee.body_char_count(jp), 2000)
            self.assertLessEqual(guarantee.body_char_count(jp), 3000)
        self.assertGreaterEqual(
            len(guarantee.unused_reserve_slugs(ROOT / "fallback" / "lhub", {})),
            14,
        )
        self.assertIn("api_payload_too_large", guarantee.FALLBACK_REASONS)

    def test_used_or_existing_reserve_is_not_selected(self):
        with tempfile.TemporaryDirectory() as tmp:
            reserve_dir = Path(tmp) / "reserve"
            reserve_dir.mkdir()
            source = json.loads(next((ROOT / "fallback" / "lhub").glob("*.json")).read_text(encoding="utf-8"))
            first = dict(source)
            first["slug"] = "used-reserve"
            second = dict(source)
            second["slug"] = "fresh-reserve"
            (reserve_dir / "01.json").write_text(json.dumps(first, ensure_ascii=False), encoding="utf-8")
            (reserve_dir / "02.json").write_text(json.dumps(second, ensure_ascii=False), encoding="utf-8")
            with mock.patch.object(guarantee, "ARTICLE_DIR", Path(tmp) / "articles"), \
                 mock.patch.object(guarantee, "ENGLISH_DIR", Path(tmp) / "articles-en"):
                chosen = guarantee.choose_reserve(
                    reserve_dir,
                    {"fallbackReserves": {"used-reserve": {"usedAt": "x"}}},
                    "2026-09-27",
                )
            self.assertIsNotNone(chosen)
            self.assertEqual(chosen[1]["slug"], "fresh-reserve")

    def test_unused_reserve_count_excludes_used_and_existing_slugs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reserve_dir = root / "reserve"
            articles = root / "articles"
            english = root / "articles-en"
            reserve_dir.mkdir()
            articles.mkdir()
            english.mkdir()
            source = json.loads(next((ROOT / "fallback" / "lhub").glob("*.json")).read_text(encoding="utf-8"))
            for slug in ("used-reserve", "existing-reserve", "fresh-reserve"):
                item = dict(source)
                item["slug"] = slug
                (reserve_dir / f"{slug}.json").write_text(json.dumps(item, ensure_ascii=False), encoding="utf-8")
            (articles / "existing-reserve.md").write_text("---\ndraft: false\n---\n", encoding="utf-8")
            with mock.patch.object(guarantee, "ARTICLE_DIR", articles), \
                 mock.patch.object(guarantee, "ENGLISH_DIR", english):
                slugs = guarantee.unused_reserve_slugs(
                    reserve_dir,
                    {"fallbackReserves": {"used-reserve": {"usedAt": "x"}}},
                )
            self.assertEqual(slugs, ["fresh-reserve"])

    def test_reserve_health_thresholds(self):
        self.assertEqual(guarantee.reserve_health(14), "healthy")
        self.assertEqual(guarantee.reserve_health(11), "healthy")
        self.assertEqual(guarantee.reserve_health(10), "warning")
        self.assertEqual(guarantee.reserve_health(8), "warning")
        self.assertEqual(guarantee.reserve_health(7), "critical")
        self.assertEqual(guarantee.reserve_health(0), "critical")

    def test_materialize_writes_pair_and_social_without_api(self):
        data = json.loads(next((ROOT / "fallback" / "lhub").glob("*.json")).read_text(encoding="utf-8"))
        jp, en = guarantee.validate_reserve(data, "2026-09-27")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with mock.patch.object(guarantee, "ARTICLE_DIR", root / "articles"), \
                 mock.patch.object(guarantee, "ENGLISH_DIR", root / "articles-en"), \
                 mock.patch.object(guarantee, "SOCIAL_DIR", root / "social"):
                guarantee.materialize_reserve(data, jp, en)
                self.assertTrue((root / "articles" / f"{data['slug']}.md").exists())
                self.assertTrue((root / "articles-en" / f"{data['slug']}.md").exists())
                for channel in ("x.md", "linkedin.md", "facebook.md"):
                    self.assertTrue((root / "social" / data["slug"] / channel).exists())

    def test_normal_path_is_not_called_when_today_is_already_published(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            articles = root / "articles"
            articles.mkdir()
            today = datetime.now(guarantee.JST).date().isoformat()
            (articles / "today.md").write_text(
                f"---\ntitle: Today\ndescription: {'a'*60}\npublishedAt: {today}\ndraft: false\nsection: lhub-usecase\n---\nbody\n",
                encoding="utf-8",
            )
            state = root / "state.json"
            reserve = root / "reserve"
            reserve.mkdir()
            argv = [
                "lhub_daily_guarantee.py",
                "--reserve-dir", str(reserve),
                "--state-path", str(state),
                "--report-path", str(root / "report.json"),
                "--",
            ]
            with mock.patch.object(guarantee, "ARTICLE_DIR", articles), \
                 mock.patch.object(sys, "argv", argv), \
                 mock.patch.object(guarantee, "run_normal_path") as normal:
                self.assertEqual(guarantee.main(), 0)
                normal.assert_not_called()


if __name__ == "__main__":
    unittest.main()
