from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class AudienceInformationArchitectureTests(unittest.TestCase):
    def read(self, relative_path: str) -> str:
        return (ROOT / relative_path).read_text(encoding="utf-8")

    def test_audience_landing_pages_exist(self):
        for path in (
            "src/pages/clinic/index.astro",
            "src/pages/for-clinics/index.astro",
            "src/pages/lhub/index.astro",
            "src/pages/world-frictions/index.astro",
            "src/pages/research/index.astro",
        ):
            self.assertTrue((ROOT / path).exists(), path)

    def test_content_schema_supports_explicit_audience_metadata(self):
        schema = self.read("src/content.config.ts")
        for field in ("audiences", "section", "industry", "series", "contentType"):
            self.assertIn(field, schema)
        self.assertIn("'world-frictions'", schema)
        self.assertIn("'editorial'", schema)

    def test_medical_topics_require_medical_context(self):
        topics = self.read("src/lib/topics.ts")
        self.assertIn("requiredKeywords: medicalContextJa", topics)
        self.assertIn("requiredKeywords: medicalContextEn", topics)
        self.assertIn("その他業種のLHub活用はLHub専用ページ", topics)

    def test_world_frictions_has_non_sales_editorial_cta_in_both_languages(self):
        ja = self.read("src/pages/articles/[...id].astro")
        en = self.read("src/pages/en/articles/[...id].astro")
        self.assertIn("editorial:", ja)
        self.assertIn("「世界の違和感」をもっと読む", ja)
        self.assertIn("editorial:", en)
        self.assertIn("Explore World Frictions", en)

    def test_homepage_exposes_clear_audience_gateways(self):
        home = self.read("src/pages/index.astro")
        for phrase in (
            "院長・クリニック関係者の方",
            "LHub導入を検討している方",
            "「世界の違和感」を読む",
            "制度・一次情報を確認したい方",
        ):
            self.assertIn(phrase, home)

    def test_existing_article_url_contract_is_preserved(self):
        ja = self.read("src/pages/articles/[...id].astro")
        self.assertIn("articles/${article.id}/", ja)
        self.assertNotIn("clinic/articles/${article.id}", ja)
        self.assertNotIn("lhub/articles/${article.id}", ja)


if __name__ == "__main__":
    unittest.main()
