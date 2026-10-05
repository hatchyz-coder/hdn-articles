import importlib.util
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import world_frictions_reserve as reserve
import generate_world_frictions as core


class WorldFrictionsReserveTests(unittest.TestCase):
    def test_provider_independent_reserve_inventory_is_replenished(self):
        paths = sorted((ROOT / "fallback" / "world-frictions").glob("*.json"))
        self.assertGreaterEqual(len(paths), 13)
        self.assertGreaterEqual(len(reserve.unused_specs()), 11)


    def test_every_reserve_passes_static_hard_contract(self):
        paths = sorted((ROOT / "fallback" / "world-frictions").glob("*.json"))
        for path in paths:
            spec = json.loads(path.read_text(encoding="utf-8"))
            candidate, sources = reserve.validate_spec(spec, check_duplicate=False)
            self.assertEqual(len(sources), 3, path.name)
            self.assertTrue(all(x["url"].startswith("https://") for x in sources), path.name)
            self.assertTrue(any(x["kind"] in {"primary", "research"} for x in sources), path.name)
            self.assertGreaterEqual(len(candidate["canonical"]["body_markdown"]), 2200, path.name)
            self.assertGreaterEqual(len(candidate["english_canonical"]["body_markdown"]), 1500, path.name)
            self.assertTrue(candidate["canonical"]["title"].startswith("【"), path.name)
            self.assertTrue(candidate["facebook"].startswith("【"), path.name)
            self.assertGreaterEqual(len(candidate["facebook"]), 1200, path.name)
            self.assertLessEqual(len(candidate["facebook"]), 1500, path.name)
            self.assertGreaterEqual(len(candidate["reposts"]), 3, path.name)

    def test_every_unused_reserve_is_not_duplicate_of_published_world_frictions(self):
        rows = reserve.unused_specs()
        self.assertGreaterEqual(len(rows), 11)
        for path, spec in rows:
            candidate, sources = reserve.validate_spec(spec, check_duplicate=True)
            self.assertTrue(candidate["publish"], path.name)
            self.assertEqual(len(sources), 3, path.name)

    def test_reserve_health_contract(self):
        self.assertEqual(reserve.reserve_health(8), "healthy")
        self.assertEqual(reserve.reserve_health(6), "healthy")
        self.assertEqual(reserve.reserve_health(5), "warning")
        self.assertEqual(reserve.reserve_health(3), "warning")
        self.assertEqual(reserve.reserve_health(2), "critical")
        self.assertEqual(reserve.reserve_health(0), "critical")

    def test_runtime_fallback_is_wired_into_multillm_runner(self):
        text = (SCRIPTS / "generate_world_frictions_multillm.py").read_text(encoding="utf-8")
        self.assertIn("PROVIDER_UNAVAILABLE_USING_RESERVE", text)
        self.assertIn("FRESH_PATH_UNAVAILABLE_USING_RESERVE", text)
        self.assertIn("reserve.materialize_reserve", text)
        self.assertIn("capture_outputs", text)
        self.assertNotIn("SKIP_PROVIDER_UNAVAILABLE", text)

    def test_workflow_exposes_reserve_inventory(self):
        text = (ROOT / ".github/workflows/world-frictions-auto-publish.yml").read_text(encoding="utf-8")
        self.assertIn("Report World Frictions reserve inventory", text)
        self.assertIn("reserve_remaining", text)
        self.assertIn("reserve_health", text)
        self.assertIn("fallback/world-frictions/**", text)


if __name__ == "__main__":
    unittest.main()
