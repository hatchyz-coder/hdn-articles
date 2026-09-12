from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "world-frictions-auto-publish.yml"
GENERATOR = ROOT / "scripts" / "generate_world_frictions.py"
CONTRACT = ROOT / "docs" / "editorial" / "world-frictions-publishing-contract.md"


class WorldFrictionsAutoPublishTests(unittest.TestCase):
    def test_workflow_has_fixed_quality_first_schedule_and_manual_entrypoint(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("cron: '30 8 * * 1,3,5'", text)
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("cancel-in-progress: false", text)
        self.assertIn("WORLD_FRICTIONS_SCORE_THRESHOLD: '86'", text)
        self.assertIn("WORLD_FRICTIONS_REVIEW_THRESHOLD: '88'", text)

    def test_no_human_confirmation_is_required_after_automated_gates(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("Merge automatically after all gates pass", text)
        self.assertIn("gh pr merge", text)
        self.assertIn("gh workflow run deploy-pages.yml", text)
        self.assertIn("Smoke test live canonical pages", text)
        self.assertNotIn("approval_required", text)
        self.assertNotIn("manual_approval", text)

    def test_generator_forces_fresh_web_search_and_independent_review(self):
        text = GENERATOR.read_text(encoding="utf-8")
        self.assertIn('"type": "web_search"', text)
        self.assertIn('"tool_choice": "required"', text)
        self.assertIn('"web_search_call.action.sources"', text)
        self.assertIn("validate_review", text)
        self.assertIn("factual confidence", text)
        self.assertIn("source quality", text)
        self.assertIn("reputational risk", text)

    def test_generator_can_skip_instead_of_publishing_filler(self):
        text = GENERATOR.read_text(encoding="utf-8")
        self.assertIn("Never publish filler", text)
        self.assertIn('publish="false"', text)
        self.assertIn("No article was published", text)

    def test_generator_produces_canonical_pair_and_distribution_bundle(self):
        text = GENERATOR.read_text(encoding="utf-8")
        self.assertIn("EN_ARTICLE_DIR", text)
        self.assertIn('"note": "note.md"', text)
        self.assertIn('"linkedin_newsletter": "linkedin-newsletter.md"', text)
        self.assertIn('"linkedin_post": "linkedin.md"', text)
        self.assertIn('"facebook": "facebook.md"', text)
        self.assertIn('"x": "x.md"', text)
        self.assertIn('"reposts": "reposts.md"', text)
        self.assertIn('"section: \\\"world-frictions\\\""', text)
        self.assertIn('"series: \\\"world-frictions\\\""', text)
        self.assertIn("cta: editorial", text)

    def test_generator_has_duplicate_and_source_grounding_gates(self):
        text = GENERATOR.read_text(encoding="utf-8")
        self.assertIn("SequenceMatcher", text)
        self.assertIn("matched < 2", text)
        self.assertIn("at least three distinct HTTPS sources", text)
        self.assertIn("at least one primary or research source", text)

    def test_contract_records_autonomous_publication_policy(self):
        text = CONTRACT.read_text(encoding="utf-8")
        self.assertIn("自動公開", text)
        self.assertIn("ハッチの事前確認を必須としません", text)
        self.assertIn("基準を満たさなければ公開しません", text)


if __name__ == "__main__":
    unittest.main()
