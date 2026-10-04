from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "scripts" / "generate_world_frictions_multillm.py"
WORKFLOW = ROOT / ".github" / "workflows" / "world-frictions-auto-publish.yml"


class WorldFrictionsMultiLLMTests(unittest.TestCase):
    def test_free_first_provider_chain_is_groq_only_by_default(self):
        text = WRAPPER.read_text(encoding="utf-8")
        self.assertIn('WORLD_FRICTIONS_PROVIDER_CHAIN","groq"', text)
        self.assertIn("GROQ_API_KEY", text)

    def test_groq_uses_current_browser_search_model(self):
        text = WRAPPER.read_text(encoding="utf-8")
        self.assertIn("openai/gpt-oss-20b", text)
        self.assertIn("DECOMMISSIONED_GROQ_MODELS", text)
        self.assertIn('"browser_search"', text)
        self.assertIn('"tool_choice"', text)
        self.assertIn("executed_tools", text)

    def test_rate_limit_stops_current_slot_without_retry_storm(self):
        text = WRAPPER.read_text(encoding="utf-8")
        self.assertIn("response.status_code==429", text)
        self.assertIn("stop this slot and use the next scheduled retry", text)

    def test_provider_outage_is_clean_skip_not_workflow_failure(self):
        text = WRAPPER.read_text(encoding="utf-8")
        self.assertIn("PROVIDER_UNAVAILABLE_USING_RESERVE", text)
        self.assertIn("reserve.materialize_reserve", text)
        self.assertIn('str(exc).startswith("All configured World Frictions providers failed:")', text)
        self.assertIn("return 0", text)

    def test_legacy_editorial_gates_remain_in_control(self):
        text = WRAPPER.read_text(encoding="utf-8")
        self.assertIn("core.call_openai=provider_call_openai", text)
        self.assertIn("result=core.main()", text)\n        self.assertIn("return result", text)

    def test_workflow_routes_through_groq_runner(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("generate_world_frictions_multillm.py", text)
        self.assertIn("WORLD_FRICTIONS_PROVIDER_CHAIN", text)
        self.assertIn("WORLD_FRICTIONS_GROQ_MODEL", text)
        self.assertIn("WORLD_FRICTIONS_GROQ_FALLBACK_MODEL", text)
        self.assertIn("GROQ_API_KEY", text)
        self.assertNotIn("WORLD_FRICTIONS_GEMINI_MODEL", text)

    def test_generation_is_split_to_avoid_oversized_requests(self):
        core = (ROOT / "scripts" / "generate_world_frictions.py").read_text(encoding="utf-8")
        self.assertIn("def discovery_prompt", core)
        self.assertIn("def writer_prompt", core)
        self.assertIn("def derivative_prompt", core)
        self.assertNotIn("max_output_tokens=28000", core)
        self.assertIn("max_output_tokens=3500", core)
        self.assertIn("max_output_tokens=6000", core)
        self.assertIn("max_output_tokens=5200", core)

    def test_only_research_and_review_calls_require_web_search(self):
        core = (ROOT / "scripts" / "generate_world_frictions.py").read_text(encoding="utf-8")
        self.assertIn("input_text=discovery_prompt", core)
        self.assertIn("input_text=writer_prompt", core)
        self.assertIn("input_text=derivative_prompt", core)
        self.assertGreaterEqual(core.count("web_search=False"), 2)
        self.assertGreaterEqual(core.count("web_search=True"), 2)


if __name__ == "__main__":
    unittest.main()
