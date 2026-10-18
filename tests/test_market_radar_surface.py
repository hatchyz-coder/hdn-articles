import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class MarketRadarSurfaceTests(unittest.TestCase):
    def test_collection_keeps_existing_article_contracts(self) -> None:
        config = (ROOT / "src/content.config.ts").read_text(encoding="utf-8")

        self.assertIn("articlesEn", config)
        self.assertIn("socialTitle", config)
        self.assertIn("'sns'", config)
        self.assertRegex(config, r"collections\s*=\s*\{\s*articles,\s*articlesEn,\s*radarReports\s*\}")

    def test_unreviewed_draft_cannot_reach_public_routes(self) -> None:
        index_page = (ROOT / "src/pages/market-radar/index.astro").read_text(encoding="utf-8")
        report_page = (ROOT / "src/pages/market-radar/reports/[slug].astro").read_text(encoding="utf-8")
        report = (
            ROOT / "src/content/radar-reports/market-radar/beauty-health-market.md"
        ).read_text(encoding="utf-8")

        self.assertIn("data.product === 'market-radar' && !data.draft", index_page)
        self.assertIn("data.product === 'market-radar' && !data.draft", report_page)
        self.assertIn("draft: true", report)
        self.assertIn("legalReview: required", report)

    def test_market_radar_styles_are_scoped_and_responsive(self) -> None:
        stylesheet = (ROOT / "src/styles/market-radar.css").read_text(encoding="utf-8")

        for broad_selector in ("body", "a", ".button", ".cta", ".article"):
            self.assertIsNone(
                re.search(rf"(?:^|}}){re.escape(broad_selector)}\{{", stylesheet)
            )
        self.assertIn("@media(max-width:820px)", stylesheet)
        self.assertIn("@media(max-width:560px)", stylesheet)

    def test_report_cta_has_source_attribution(self) -> None:
        report_page = (ROOT / "src/pages/market-radar/reports/[slug].astro").read_text(encoding="utf-8")

        self.assertIn("cta_source=market-radar", report_page)
        self.assertIn("cta_position=report_end", report_page)


if __name__ == "__main__":
    unittest.main()
