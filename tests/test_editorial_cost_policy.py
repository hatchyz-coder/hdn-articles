from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class EditorialCostPolicyTests(unittest.TestCase):
    def test_daily_workflow_uses_cost_optimized_runner(self):
        workflow = (ROOT / ".github/workflows/daily-drive-editorial-publish.yml").read_text(encoding="utf-8")
        self.assertIn("generate_from_drive_editorial_cost_optimized.py", workflow)
        self.assertIn("OPENAI_MAX_ATTEMPTS: '2'", workflow)
        self.assertIn("OPENAI_READ_TIMEOUT_SECONDS: '180'", workflow)

    def test_drive_openai_calls_are_bounded(self):
        source = (ROOT / "scripts/generate_from_drive_editorial_cost_optimized.py").read_text(encoding="utf-8")
        self.assertIn('"max_tool_calls": 2', source)
        self.assertIn('"reasoning": {"effort": "low"}', source)
        self.assertIn('"search_context_size": "low"', source)
        self.assertIn('"prompt_cache_key": "hdn-drive-editorial-v3"', source)
        self.assertIn('OPENAI_MAX_OUTPUT_TOKENS', source)
        self.assertIn('estimatedOpenAiCostUsd', source)

    def test_official_source_uses_cost_optimized_runner(self):
        workflow = (ROOT / ".github/workflows/official-source-daily-publish.yml").read_text(encoding="utf-8")
        self.assertIn("generate_content_cost_optimized.py", workflow)
        source = (ROOT / "scripts/generate_content_cost_optimized.py").read_text(encoding="utf-8")
        self.assertIn('"reasoning": {"effort": "low"}', source)
        self.assertIn('"prompt_cache_key": "hdn-official-source-v2"', source)
        self.assertNotIn('"web_search"', source)

    def test_fallback_does_not_loop_paid_workflows(self):
        fallback = (ROOT / ".github/workflows/daily-drive-editorial-fallback.yml").read_text(encoding="utf-8")
        self.assertNotIn("for attempt in 1 2 3 4", fallback)
        self.assertEqual(fallback.count("gh workflow run daily-drive-editorial-publish.yml"), 1)


if __name__ == "__main__":
    unittest.main()
