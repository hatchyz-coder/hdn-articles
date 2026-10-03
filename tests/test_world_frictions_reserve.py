import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import world_frictions_reserve as reserve


class WorldFrictionsReserveTests(unittest.TestCase):
    def test_reserve_bundle_is_complete_and_finalizable(self):
        paths = sorted((ROOT / "fallback" / "world-frictions").glob("*.json"))
        self.assertGreaterEqual(len(paths), 1)
        data = json.loads(paths[0].read_text(encoding="utf-8"))
        self.assertIn("section: \"world-frictions\"", data["jp"])
        self.assertIn("series: \"world-frictions\"", data["jp"])
        self.assertIn("cta: editorial", data["jp"])
        self.assertIn("## 出典・一次情報・参考文献", data["jp"])
        self.assertIn("section: \"world-frictions\"", data["en"])
        required = {"note.md", "linkedin-newsletter.md", "linkedin.md", "facebook.md", "x.md", "reposts.md"}
        self.assertEqual(set(data["social"]), required)
        self.assertGreaterEqual(len(data["social"]["facebook.md"]), 1200)
        self.assertLessEqual(len(data["social"]["facebook.md"]), 1500)
        for name, text in data["social"].items():
            self.assertNotIn("*", text, name)
            if name != "reposts.md":
                self.assertIn("{{URL}}", text, name)

    def test_materialize_writes_pair_and_distribution_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            source_dir = root / "reserve"
            source_dir.mkdir()
            source = json.loads(
                next((ROOT / "fallback" / "world-frictions").glob("*.json")).read_text(encoding="utf-8")
            )
            (source_dir / "01.json").write_text(json.dumps(source, ensure_ascii=False), encoding="utf-8")
            with mock.patch.object(reserve, "RESERVE_DIR", source_dir), \
                 mock.patch.object(reserve, "ARTICLE_DIR", root / "articles"), \
                 mock.patch.object(reserve, "EN_ARTICLE_DIR", root / "articles-en"), \
                 mock.patch.object(reserve, "SOCIAL_DIR", root / "social"):
                result = reserve.materialize_next_reserve("api_rate_limited")
            self.assertIsNotNone(result)
            slug = source["slug"]
            self.assertTrue((root / "articles" / f"{slug}.md").exists())
            self.assertTrue((root / "articles-en" / f"{slug}.md").exists())
            for name in source["social"]:
                self.assertTrue((root / "social" / slug / name).exists())
            facebook = (root / "social" / slug / "facebook.md").read_text(encoding="utf-8")
            self.assertIn(f"https://article.hdnjapan.com/articles/{slug}/", facebook)
            self.assertNotIn("{{DATE}}", (root / "articles" / f"{slug}.md").read_text(encoding="utf-8"))

    def test_published_slug_is_not_reused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            source_dir = root / "reserve"
            articles = root / "articles"
            english = root / "articles-en"
            source_dir.mkdir()
            articles.mkdir()
            english.mkdir()
            source = json.loads(
                next((ROOT / "fallback" / "world-frictions").glob("*.json")).read_text(encoding="utf-8")
            )
            (source_dir / "01.json").write_text(json.dumps(source, ensure_ascii=False), encoding="utf-8")
            (articles / f"{source['slug']}.md").write_text("---\ndraft: false\n---\n", encoding="utf-8")
            with mock.patch.object(reserve, "RESERVE_DIR", source_dir), \
                 mock.patch.object(reserve, "ARTICLE_DIR", articles), \
                 mock.patch.object(reserve, "EN_ARTICLE_DIR", english):
                self.assertIsNone(reserve.choose_reserve())


if __name__ == "__main__":
    unittest.main()
