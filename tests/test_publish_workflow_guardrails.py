from pathlib import Path
import unittest


WORKFLOW = Path('.github/workflows/publish-approved-article.yml')


class PublishWorkflowGuardrailTests(unittest.TestCase):
    def test_publish_workflow_keeps_explicit_approval_gate(self):
        text = WORKFLOW.read_text(encoding='utf-8')
        self.assertIn("github.event.comment.body == '/publish'", text)
        self.assertIn('OWNER', text)
        self.assertIn('COLLABORATOR', text)

    def test_publish_workflow_requires_single_draft_article(self):
        text = WORKFLOW.read_text(encoding='utf-8')
        self.assertIn('Expected exactly one changed article', text)
        self.assertIn("grep -q '^draft: true$'", text)
        self.assertIn("'draft: false'", text)

    def test_publish_workflow_runs_full_validation(self):
        text = WORKFLOW.read_text(encoding='utf-8')
        for label in ['Lint', 'Typecheck', 'Tests', 'Build', 'Migration check']:
            self.assertIn(f'- name: {label}', text)

    def test_publish_workflow_dispatches_and_waits_for_pages(self):
        text = WORKFLOW.read_text(encoding='utf-8')
        self.assertIn('actions: write', text)
        self.assertIn('gh workflow run deploy-pages.yml', text)
        self.assertIn('gh run watch', text)
        self.assertIn('--exit-status', text)


if __name__ == '__main__':
    unittest.main()
