from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
WORKFLOW=ROOT/'.github/workflows/world-frictions-completion-gate.yml'
CONTRACT=ROOT/'docs/world_frictions_publication_completion_gate.md'

class CompletionWorkflowTests(unittest.TestCase):
    def test_completion_workflow_runs_after_auto_publish(self):
        text=WORKFLOW.read_text(encoding='utf-8')
        self.assertIn('World Frictions Auto Publish',text)
        self.assertIn('Pass 1 artifact completeness',text)
        self.assertIn('Pass 2 canonical production verification',text)
    def test_workflow_never_infers_social_live(self):
        text=WORKFLOW.read_text(encoding='utf-8')
        self.assertIn('Social state is intentionally not inferred here.',text)
        self.assertIn('SOCIAL_LIVE requires direct destination evidence',text)
    def test_contract_and_machine_gate_share_state_names(self):
        contract=CONTRACT.read_text(encoding='utf-8'); workflow=WORKFLOW.read_text(encoding='utf-8')
        self.assertIn('CANONICAL_LIVE',contract); self.assertIn('CANONICAL_LIVE',workflow)
        self.assertIn('SOCIAL_LIVE',contract); self.assertIn('SOCIAL_LIVE',workflow)

if __name__=='__main__': unittest.main()
