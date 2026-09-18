import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from publication_completion_gate import Evidence, State, facebook_copy_valid, may_claim_social_published, resolve_state


class PublicationCompletionGateTests(unittest.TestCase):
    def test_1_missing_english_pair_is_not_published(self):
        e = Evidence(jp_exists=True, en_exists=False)
        self.assertEqual(resolve_state(e), State.CANONICAL_COMMITTED)
        self.assertFalse(may_claim_social_published(e))

    def test_2_merged_but_live_404_is_not_published(self):
        e = Evidence(jp_exists=True, en_exists=True, canonical_live=False)
        self.assertEqual(resolve_state(e), State.CANONICAL_COMMITTED)

    def test_3_pending_social_is_only_scheduled(self):
        e = Evidence(jp_exists=True, en_exists=True, canonical_live=True, social_provider_id="377016188", social_status="PENDING")
        self.assertEqual(resolve_state(e), State.SOCIAL_SCHEDULED)
        self.assertFalse(may_claim_social_published(e))

    def test_4_scheduler_disappearance_without_live_evidence_is_not_success(self):
        e = Evidence(jp_exists=True, en_exists=True, canonical_live=True, social_provider_id="377016188", social_status="")
        self.assertEqual(resolve_state(e), State.SOCIAL_SCHEDULED)
        self.assertFalse(may_claim_social_published(e))

    def test_5_facebook_copy_outside_editorial_target_fails(self):
        self.assertFalse(facebook_copy_valid(900))
        self.assertTrue(facebook_copy_valid(1200))
        self.assertTrue(facebook_copy_valid(1500))
        self.assertFalse(facebook_copy_valid(1501))

    def test_social_live_requires_direct_evidence_and_duplicate_reconciliation(self):
        e = Evidence(jp_exists=True, en_exists=True, canonical_live=True, social_provider_id="x", social_status="PUBLISHED", social_live_evidence=True, social_evidence_source="direct_network", duplicate_free=True)
        self.assertEqual(resolve_state(e), State.SOCIAL_LIVE)
        self.assertTrue(may_claim_social_published(e))


if __name__ == "__main__":
    unittest.main()
