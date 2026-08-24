from pathlib import Path
import unittest


PUBLISH = Path('.github/workflows/daily-drive-editorial-publish.yml')
FALLBACK = Path('.github/workflows/daily-drive-editorial-fallback.yml')


class DailyDrivePublicationGuardrailTests(unittest.TestCase):
    def test_daily_workflow_requires_production_pair_verification(self):
        text = PUBLISH.read_text(encoding='utf-8')
        self.assertIn('reconcile_editorial_publication_state.py', text)
        self.assertIn('--required-slug "$SLUG"', text)
        self.assertIn('Persist merged state before deploy', text)
        self.assertIn('Persist publication-confirmed state', text)
        self.assertIn('Both production URLs returned 2xx', text)

    def test_fallback_does_not_count_unverified_generated_state(self):
        text = FALLBACK.read_text(encoding='utf-8')
        self.assertIn("{'published', 'published_manual'}", text)
        self.assertNotIn("{'generated', 'published_manual'}", text)
        self.assertIn("record.get('publishedAt') or record.get('finishedAt')", text)

    def test_fallback_waits_for_active_regular_run_before_recovery(self):
        text = FALLBACK.read_text(encoding='utf-8')
        self.assertIn('Wait for regular publication slot to settle', text)
        self.assertIn('.status == "in_progress" or .status == "queued"', text)
        self.assertIn('Waiting for active publication run', text)

    def test_backlog_scan_is_not_limited_to_recent_500(self):
        text = PUBLISH.read_text(encoding='utf-8')
        self.assertIn('--max-drive-files 5000', text)


if __name__ == '__main__':
    unittest.main()
