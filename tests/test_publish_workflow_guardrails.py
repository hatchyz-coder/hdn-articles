from pathlib import Path
import unittest


WORKFLOW = Path('.github/workflows/publish-approved-article.yml')


class PublishWorkflowGuardrailTests(unittest.TestCase):
    def test_publish_workflow_keeps_explicit_approval_gate(self):
        text = WORKFLOW.read_text(encoding='utf-8')
        self.assertIn("github.event.comment.body == '/publish'", text)
        self.assertIn('OWNER', text)
        self.assertIn('COLLABORATOR', text)

    def test_publish_workflow_requires_paired_draft_articles(self):
        text = WORKFLOW.read_text(encoding='utf-8')
        self.assertIn('Expected exactly one changed article', text)
        self.assertIn('Expected exactly one changed English article', text)
        self.assertIn('Japanese/English article slugs do not match', text)
        self.assertIn("grep -q '^draft: true$'", text)
        self.assertIn("'draft: false'", text)
        self.assertIn('ENGLISH_ARTICLE_PATH', text)

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

    def test_publication_confirmation_includes_both_urls_and_three_social_channels(self):
        text = WORKFLOW.read_text(encoding='utf-8')
        self.assertIn('https://article.hdnjapan.com/articles/{slug}/', text)
        self.assertIn('https://article.hdnjapan.com/en/articles/{slug}/', text)
        for label in ['### X', '### LinkedIn', '### Facebook']:
            self.assertIn(label, text)
        for filename in ['x.md', 'linkedin.md', 'facebook.md']:
            self.assertIn(filename, text)
        for label in ['X用リンク', 'LinkedIn用リンク', 'Facebook用リンク']:
            self.assertIn(label, text)


if __name__ == '__main__':
    unittest.main()
