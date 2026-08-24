import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import reconcile_editorial_publication_state as reconcile


class ReconcileEditorialPublicationStateTests(unittest.TestCase):
    def test_article_urls_include_japanese_and_english_routes(self):
        jp, en = reconcile.article_urls("example")
        self.assertEqual(jp, "https://article.hdnjapan.com/articles/example/")
        self.assertEqual(en, "https://article.hdnjapan.com/en/articles/example/")

    @patch.object(reconcile, "pair_is_live", return_value=True)
    def test_live_generated_record_is_promoted(self, _mock):
        state = {"documents": {"x": {"status": "generated", "slug": "example"}}}
        promoted, required_live = reconcile.reconcile_state(state, reconcile.DEFAULT_BASE_URL, "example", 1, 0)
        self.assertEqual(promoted, 1)
        self.assertTrue(required_live)
        self.assertEqual(state["documents"]["x"]["status"], "published")
        self.assertIn("publishedAt", state["documents"]["x"])

    @patch.object(reconcile, "pair_is_live", return_value=False)
    def test_unverified_generated_record_is_not_promoted(self, _mock):
        state = {"documents": {"x": {"status": "generated", "slug": "example"}}}
        promoted, required_live = reconcile.reconcile_state(state, reconcile.DEFAULT_BASE_URL, "example", 1, 0)
        self.assertEqual(promoted, 0)
        self.assertFalse(required_live)
        self.assertEqual(state["documents"]["x"]["status"], "generated")


if __name__ == "__main__":
    unittest.main()
