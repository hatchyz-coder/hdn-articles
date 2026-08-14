from pathlib import Path
import tempfile
import unittest

from scripts.finalize_social_posts import clean_x_body


class FinalizeSocialPostsTests(unittest.TestCase):
    def test_clean_x_body_removes_existing_url_and_suffix(self):
        text = "重要な論点です。\n\n続きはこちら\nhttps://example.com/articles/test/"
        self.assertEqual(clean_x_body(text), "重要な論点です。")

    def test_clean_x_body_caps_long_copy(self):
        cleaned = clean_x_body("あ" * 260)
        self.assertLessEqual(len(cleaned), 208)
        self.assertTrue(cleaned.endswith("…"))

    def test_clean_x_body_preserves_problem_and_key_points(self):
        text = "クリニックはここを見落としていませんか。\n\n重要なのは患者説明と運用記録です。"
        self.assertEqual(clean_x_body(text), text)


if __name__ == "__main__":
    unittest.main()
