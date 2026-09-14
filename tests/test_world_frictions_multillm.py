from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "scripts" / "generate_world_frictions_multillm.py"
WORKFLOW = ROOT / ".github" / "workflows" / "world-frictions-auto-publish.yml"


class WorldFrictionsMultiLLMTests(unittest.TestCase):
    def test_free_first_provider_chain_is_configured(self):
        text = WRAPPER.read_text(encoding="utf-8")
        self.assertIn('"gemini,groq,openai"', text)
        self.assertIn("GEMINI_API_KEY", text)
        self.assertIn("GROQ_API_KEY", text)
        self.assertIn("OPENAI_API_KEY", text)

    def test_gemini_uses_google_search_grounding(self):
        text = WRAPPER.read_text(encoding="utf-8")
        self.assertIn('"google_search": {}', text)
        self.assertIn("groundingChunks", text)
        self.assertIn("gemini-2.5-flash", text)

    def test_groq_uses_compound_web_search(self):
        text = WRAPPER.read_text(encoding="utf-8")
        self.assertIn("groq/compound", text)
        self.assertIn('"web_search"', text)
        self.assertIn('"visit_website"', text)
        self.assertIn("executed_tools", text)

    def test_legacy_editorial_gates_remain_in_control(self):
        text = WRAPPER.read_text(encoding="utf-8")
        self.assertIn("core.call_openai = provider_call_openai", text)
        self.assertIn("return core.main()", text)

    def test_workflow_routes_through_multillm_runner(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("generate_world_frictions_multillm.py", text)
        self.assertIn("WORLD_FRICTIONS_PROVIDER_CHAIN", text)
        self.assertIn("WORLD_FRICTIONS_GEMINI_MODEL", text)
        self.assertIn("WORLD_FRICTIONS_GROQ_MODEL", text)


if __name__ == "__main__":
    unittest.main()
