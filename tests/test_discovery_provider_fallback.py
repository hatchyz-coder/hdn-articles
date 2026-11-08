import sys
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import discover_sources as discovery


class DiscoveryFallbackTests(unittest.TestCase):
    def setUp(self):
        self.candidates = [
            {"title": "Clinic booking compliance", "url": "https://example.org/one",
             "source": "official", "keyword_score": 4, "source_priority": 2},
        ]

    def test_openai_503_is_optional_and_keeps_candidates(self):
        response = Mock()
        response.raise_for_status.side_effect = discovery.requests.HTTPError("503 Service Unavailable")
        with patch.dict(discovery.os.environ, {"OPENAI_API_KEY": "dummy"}), \
             patch.object(discovery.requests, "post", return_value=response):
            ranked = discovery.ai_rank([dict(x) for x in self.candidates])
        self.assertEqual(ranked[0]["url"], self.candidates[0]["url"])
        self.assertEqual(ranked[0]["keyword_score"], 4)

    def test_invalid_provider_json_keeps_official_candidates(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"output_text": "invalid JSON"}
        with patch.dict(discovery.os.environ, {"OPENAI_API_KEY": "dummy"}), \
             patch.object(discovery.requests, "post", return_value=response):
            ranked = discovery.ai_rank([dict(x) for x in self.candidates])
        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0]["source"], "official")


if __name__ == "__main__":
    unittest.main()
