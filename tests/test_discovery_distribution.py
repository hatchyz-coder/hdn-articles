from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DiscoveryDistributionTests(unittest.TestCase):
    def read(self, path: str) -> str:
        return (ROOT / path).read_text(encoding="utf-8")

    def test_all_articles_discovery_route_exists_with_static_cards(self):
        page = self.read("src/pages/articles/index.astro")
        self.assertIn("記事を探す", page)
        self.assertIn("data-discovery-card", page)
        self.assertIn("getCollection('articles'", page)
        self.assertIn("URLSearchParams", page)
        self.assertIn("name=\"audience\"", page)
        self.assertIn("name=\"section\"", page)
        self.assertIn("name=\"industry\"", page)
        self.assertIn("name=\"sort\"", page)

    def test_search_analytics_does_not_send_query_text(self):
        page = self.read("src/pages/articles/index.astro")
        event_start = page.index("'article_search_usage'")
        event_end = page.index("});", event_start)
        event_block = page[event_start:event_end]
        self.assertIn("has_query", event_block)
        self.assertIn("results_count", event_block)
        for forbidden in ("query_text", "search_query", "search_term", "raw_query"):
            self.assertNotIn(forbidden, event_block)

    def test_distribution_urls_are_explicit_and_optional(self):
        config = self.read("src/lib/distribution.ts")
        self.assertIn("https://article.hdnjapan.com/", config)
        self.assertIn("https://jp.linkedin.com/in/tsuyoshi-hadano", config)
        self.assertIn("PUBLIC_LINKEDIN_NEWSLETTER_URL", config)
        self.assertIn("PUBLIC_NOTE_URL", config)

    def test_world_frictions_distribution_is_reader_facing(self):
        page = self.read("src/pages/world-frictions/index.astro")
        self.assertIn("読みやすい場所で、続きを追えます。", page)
        self.assertIn("LinkedIn", page)
        self.assertIn("note", page)
        self.assertIn('data-distribution-channel="note"', page)
        for internal_copy in (
            "正本はHDN",
            "Newsletterの購読URLを設定するまでは",
            "公開導線を準備中",
            "営業記事ではなく",
            "順次移します",
        ):
            self.assertNotIn(internal_copy, page)

    def test_primary_navigation_links_to_discovery(self):
        layout = self.read("src/layouts/BaseLayout.astro")
        self.assertIn("articles/", layout)
        self.assertIn("記事を探す", layout)
        self.assertIn("article_to_newsletter_click", layout)
        self.assertIn("article_to_note_click", layout)
        self.assertIn("world_frictions_related_click", layout)


if __name__ == "__main__":
    unittest.main()
