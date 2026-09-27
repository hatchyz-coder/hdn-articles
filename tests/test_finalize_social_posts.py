from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.finalize_social_posts import clean_social_body, clean_x_body, finalize_social_posts, validate_social_copy


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
            url = "https://article.hdnjapan.com/articles/test-article/"
            (folder / "x.md").write_text("【違和感】\n短い論点です。\n\n" + url, encoding="utf-8")
            (folder / "linkedin.md").write_text("【日本語 / English】\n日本語の経営論点です。\n\nEnglish follows below.\nA business implication.\n\n" + url, encoding="utf-8")
            fb = "【Facebookタイトル】\n" + ("読者価値のある本文です。" * 100) + "\n" + url
            fb = fb[:1300-len(url)-1] + "\n" + url
            (folder / "facebook.md").write_text(fb, encoding="utf-8")

            with patch("scripts.finalize_social_posts.SOCIAL_DIR", social_root):
                paths = finalize_social_posts("test-article")

            self.assertEqual(len(paths), 3)
            self.assertIn("続きはこちら\n" + url, (folder / "x.md").read_text(encoding="utf-8"))
            self.assertIn("記事はこちら\n" + url, (folder / "linkedin.md").read_text(encoding="utf-8"))
            self.assertIn("記事はこちら\n" + url, (folder / "facebook.md").read_text(encoding="utf-8"))

    def test_validate_social_copy_rejects_facebook_under_1200(self):
        url = "https://article.hdnjapan.com/articles/test/"
        with self.assertRaisesRegex(ValueError, "1200-1500"):
            validate_social_copy("facebook", "【短い】\n本文\n" + url, url)

    def test_validate_social_copy_requires_linkedin_bilingual_contract(self):
        url = "https://article.hdnjapan.com/articles/test/"
        with self.assertRaisesRegex(ValueError, "English follows"):
            validate_social_copy("linkedin", "【日本語 / English】\n日本語だけ\n" + url, url)

    def test_validate_social_copy_requires_x_title(self):
        url = "https://article.hdnjapan.com/articles/test/"
        with self.assertRaisesRegex(ValueError, "title"):
            validate_social_copy("x", "タイトルなし\n" + url, url)


if __name__ == "__main__":
    unittest.main()
