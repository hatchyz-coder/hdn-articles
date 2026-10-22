from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class GrowthPipelineResilienceTests(unittest.TestCase):
    def test_generator_uses_dedicated_rate_limit_exit_code(self):
        text = (ROOT / "scripts" / "generate_content.py").read_text(encoding="utf-8")
        self.assertIn('"api_rate_limited" in str(exc)', text)
        self.assertIn('"api_payload_too_large" in str(exc)', text)
        self.assertIn("response.status_code == 413", text)
        self.assertIn("SystemExit(75)", text)

    def test_workflow_cleanly_defers_provider_size_or_rate_limit_and_retries_same_day(self):
        text = (ROOT / ".github" / "workflows" / "hdn-growth-pipeline.yml").read_text(encoding="utf-8")
        self.assertIn("id: generate", text)
        self.assertIn('if [ "$rc" -eq 75 ]; then', text)
        self.assertIn('echo "generated=false" >> "$GITHUB_OUTPUT"', text)
        self.assertIn("candidate remains eligible for a later same-day slot", text)
        self.assertIn("steps.generate.outputs.generated == 'true'", text)
        self.assertIn("cron: '15 22 * * 1-5'", text)
        self.assertIn("cron: '45 1 * * 1-5'", text)
        self.assertIn("cron: '45 5 * * 1-5'", text)


if __name__ == "__main__":
    unittest.main()
