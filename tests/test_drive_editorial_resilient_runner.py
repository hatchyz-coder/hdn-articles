import json
import sys
import tempfile
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

    def test_parse_github_outputs_uses_last_value(self):
        outputs = resilient.parse_github_outputs("selected=false\nreason=api_timeout\nreason=generated\n")
        self.assertEqual(outputs["selected"], "false")
        self.assertEqual(outputs["reason"], "generated")

    def test_generator_outputs_supply_reason_missing_from_report(self):
        report = resilient.apply_generator_outputs(
            {"selected": False},
            {"selected": "false", "reason": "api_timeout"},
        )
        self.assertFalse(report["selected"])
        self.assertEqual(report["reason"], "api_timeout")

    def test_generator_outputs_can_mark_selection(self):
        report = resilient.apply_generator_outputs(
            {"selected": False},
            {"selected": "true", "reason": "generated", "slug": "example"},
        )
        self.assertTrue(report["selected"])
        self.assertEqual(report["reason"], "generated")

    def test_generator_arg_value(self):
        args = ["--folder-id", "folder", "--state-path", "state.json", "--min-score", "72"]
        self.assertEqual(resilient.generator_arg_value(args, "--state-path"), "state.json")
        self.assertIsNone(resilient.generator_arg_value(args, "--missing"))

    def test_requeues_only_legacy_ai_confidentiality_once(self):
        state = {
            "documents": {
                "ai-old": {
                    "status": "skipped_confidential",
                    "reason": "AI confidentiality flags",
                    "retry_count": 1,
                },
                "heuristic": {
                    "status": "skipped_confidential",
                    "reason": "confidentiality heuristic matched",
                    "retry_count": 0,
                },
                "already-migrated": {
                    "status": "skipped_confidential",
                    "reason": "AI confidentiality flags",
                    "privacyContractVersion": resilient.PRIVACY_CONTRACT_VERSION,
                },
                "published": {"status": "published", "reason": "generated"},
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            path.write_text(json.dumps(state), encoding="utf-8")
            self.assertEqual(resilient.requeue_legacy_false_confidential(path), 1)
            updated = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(updated["documents"]["ai-old"]["status"], "api_timeout")
            self.assertEqual(updated["documents"]["ai-old"]["retry_count"], 0)
            self.assertEqual(
                updated["documents"]["ai-old"]["privacyContractVersion"],
                resilient.PRIVACY_CONTRACT_VERSION,
            )
            self.assertEqual(updated["documents"]["heuristic"]["status"], "skipped_confidential")
            self.assertEqual(updated["documents"]["already-migrated"]["status"], "skipped_confidential")
            self.assertEqual(resilient.requeue_legacy_false_confidential(path), 0)


if __name__ == "__main__":
    unittest.main()
