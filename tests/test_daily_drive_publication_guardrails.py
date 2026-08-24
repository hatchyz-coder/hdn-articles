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
        self.assertIn('--retries 36', text)

    def test_fallback_does_not_count_unverified_generated_state(self):
        text = FALLBACK.read_text(encoding='utf-8')
        self.assertIn("{'published', 'published_manual'}", text)
        self.assertNotIn("{'generated', 'published_manual'}", text)
        self.assertIn("record.get('publishedAt') or record.get('finishedAt')", text)

    def test_backlog_scan_is_not_limited_to_recent_500(self):
        text = PUBLISH.read_text(encoding='utf-8')
        self.assertIn('--max-drive-files 5000', text)

    def test_slot_rotates_past_unsuitable_candidates(self):
        text = PUBLISH.read_text(encoding='utf-8')
        self.assertIn('MAX_CANDIDATE_TRIES=3', text)
        self.assertIn('Editorial candidate attempt', text)
        self.assertIn('candidate rotation', text)

    def test_manual_quality_input_cannot_lower_production_floor(self):
        text = PUBLISH.read_text(encoding='utf-8')
        self.assertIn('if [ "$REQUESTED_MIN_SCORE" -lt 72 ]', text)
        self.assertIn('MIN_SCORE=72', text)

    def test_publisher_does_not_launch_duplicate_pages_deployment(self):
        text = PUBLISH.read_text(encoding='utf-8')
        self.assertIn('Observe push-triggered Pages deployment', text)
        self.assertNotIn('gh workflow run deploy-pages.yml --ref main', text)
        self.assertIn('verification below remains authoritative', text)

    def test_fallback_waits_for_active_regular_slot_before_recovery(self):
        text = FALLBACK.read_text(encoding='utf-8')
        self.assertIn('Wait for regular publication slot to settle', text)
        self.assertIn('gh run watch "$active_id" --exit-status || true', text)


if __name__ == '__main__':
    unittest.main()
