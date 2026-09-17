import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from validate_world_frictions_completion import evaluate


SLUG = "sample-friction"


def valid_evidence():
    return {
        "slug": SLUG,
        "jp_exists": True,
        "en_exists": True,
        "canonical_live": True,
        "social_provider_id": "provider-1",
        "social_status": "PUBLISHED",
        "social_live_evidence": True,
        "social_evidence_source": "provider_published_retrieval",
        "duplicate_free": True,
        "facebook_chars": 1300,
    }


class WorldFrictionsCompletionGateTests(unittest.TestCase):
    def assert_incomplete(self, changes):
        evidence = valid_evidence(); evidence.update(changes)
        self.assertEqual("INCOMPLETE", evaluate(SLUG, evidence)["result"])

    def test_1_jp_without_english_is_incomplete(self):
        self.assert_incomplete({"en_exists": False})

    def test_2_merged_but_production_404_is_incomplete(self):
        self.assert_incomplete({"canonical_live": False})

    def test_3_pending_facebook_is_incomplete(self):
        self.assert_incomplete({"social_status": "PENDING", "social_live_evidence": False, "social_evidence_source": ""})

    def test_4_scheduler_disappearance_without_evidence_is_incomplete(self):
        self.assert_incomplete({"social_status": "", "social_live_evidence": False, "social_evidence_source": ""})

    def test_5_short_facebook_is_incomplete(self):
        self.assert_incomplete({"facebook_chars": 900})

    def test_normal_case_is_completed(self):
        self.assertEqual("COMPLETED", evaluate(SLUG, valid_evidence())["result"])

    def test_untrusted_evidence_source_is_incomplete(self):
        self.assert_incomplete({"social_evidence_source": "scheduler_disappearance"})


if __name__ == "__main__":
    unittest.main()
