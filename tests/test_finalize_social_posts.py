from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.finalize_social_posts import clean_social_body, clean_x_body, finalize_social_posts


class FinalizeSocialPostsTests(unittest.TestCase):
    def test_clean_x_body_removes_existing_url_and_suffix(self):
        text = "重要な論点です。\n\n続きはこちら\nhttps://example.com/articles/test/"
        self.assertEqual(clean_x_body(text), "重要な論点です。")

    def test_clean_x_body_caps_long_copy(self):
        cleaned = clean_x_body("あ" * 260)
        self.assertLessEqual(len(cleaned), 208)
        self.assertTrue(cleaned.endswith("…"))

    def test_clean_social_body_removes_existing_destination(self):
        text = "実務上の確認ポイントです。\n\n記事はこちら\nhttps://example.com/articles/test/"
        self.assertEqual(clean_social_body(text), "実務上の確認ポイントです。")

    def test_finalize_social_posts_adds_same_production_url_to_all_channels(self):
        with tempfile.TemporaryDirectory() as tmp:
            social_root = Path(tmp) / "social"
            folder = social_root / "test-article"
            folder.mkdir(parents=True)
            (folder / "x.md").write_text("問題提起です。", encoding="utf-8")
            (folder / "linkedin.md").write_text("LinkedIn本文です。", encoding="utf-8")
            (folder / "facebook.md").write_text("Facebook本文です。", encoding="utf-8")

            with patch("scripts.finalize_social_posts.SOCIAL_DIR", social_root):
                paths = finalize_social_posts("test-article")

            self.assertEqual(len(paths), 3)
            url = "https://article.hdnjapan.com/articles/test-article/"
            self.assertIn("続きはこちら\n" + url, (folder / "x.md").read_text(encoding="utf-8"))
            self.assertIn("記事はこちら\n" + url, (folder / "linkedin.md").read_text(encoding="utf-8"))
            self.assertIn("記事はこちら\n" + url, (folder / "facebook.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
