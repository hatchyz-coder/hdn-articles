import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import run_drive_editorial_resilient as resilient


class DriveEditorialResilientRunnerTests(unittest.TestCase):
    def test_selected_article_stops_immediately(self):
        retry, reason = resilient.should_continue(0, {"selected": True, "reason": "generated"})
        self.assertFalse(retry)
        self.assertEqual(reason, "selected")

    def test_api_timeout_retries_same_slot(self):
        retry, reason = resilient.should_continue(0, {"selected": False, "reason": "api_timeout"})
        self.assertTrue(retry)
        self.assertEqual(reason, "api_timeout")

    def test_low_score_rotates_to_next_candidate_without_lowering_gate(self):
        retry, reason = resilient.should_continue(0, {"selected": False, "reason": "low_score"})
        self.assertTrue(retry)
        self.assertEqual(reason, "low_score")

    def test_confidential_seed_rotates_to_next_candidate(self):
        retry, reason = resilient.should_continue(0, {"selected": False, "reason": "confidential"})
        self.assertTrue(retry)
        self.assertEqual(reason, "confidential")

    def test_no_candidate_stops_cleanly(self):
        retry, reason = resilient.should_continue(0, {"selected": False, "reason": "no_candidate"})
        self.assertFalse(retry)
        self.assertEqual(reason, "no_candidate")

    def test_nonzero_generator_failure_is_retried(self):
        retry, reason = resilient.should_continue(1, {})
        self.assertTrue(retry)
        self.assertEqual(reason, "generator_error")


if __name__ == "__main__":
    unittest.main()
