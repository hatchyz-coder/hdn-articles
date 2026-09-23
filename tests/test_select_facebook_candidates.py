import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("selector", ROOT / "scripts/select_facebook_candidates.py")
selector = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = selector
SPEC.loader.exec_module(selector)


class FacebookCandidateTests(unittest.TestCase):
    def fixture(self, *, draft="false", copy="【題】\n" + "判断と具体例です。" * 140, sources=2):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        article_dir, social_dir = root / "articles", root / "social"
        article_dir.mkdir(); (social_dir / "sample").mkdir(parents=True)
        links = "\n".join(f"https://example{i}.org/source" for i in range(sources))
        body = ("\n## 判断\n私は違和感を持ち、必要な設計と確認を判断します。調査2026事例報告1。" * 8) + links
        (article_dir / "sample.md").write_text(f'---\ntitle: "題"\ncategory: "医療"\ndraft: {draft}\n---\n{body}', encoding="utf-8")
        (social_dir / "sample" / "facebook.md").write_text(copy, encoding="utf-8")
        return temp, article_dir / "sample.md", social_dir

    def evaluate(self, **kwargs):
        temp, article, social = self.fixture(**kwargs)
        self.addCleanup(temp.cleanup)
        with patch.object(selector, "SOCIAL_DIR", social):
            return selector.evaluate(article, {}, "2026-09-25T19:30:00+09:00")

    def test_selects_substantive_published_candidate(self):
        self.assertEqual(self.evaluate().decision, "candidate_selected")

    def test_publication_failure_is_distinct(self):
        self.assertEqual(self.evaluate(draft="true").decision_reason, "canonical_not_published")

    def test_missing_copy_is_rejected(self):
        self.assertEqual(self.evaluate(copy="").decision_reason, "facebook_copy_missing")

    def test_quality_shortfall_is_rejected(self):
        self.assertIn("facebook_copy_not_standalone", self.evaluate(copy="【短い】").decision_reason)

    def test_duplicate_is_not_selected(self):
        record = self.evaluate()
        temp, article, social = self.fixture()
        self.addCleanup(temp.cleanup)
        with patch.object(selector, "SOCIAL_DIR", social):
            duplicate = selector.evaluate(article, {record.duplicate_key: {"status": "published", "metricool_post_id": "1"}}, None)
        self.assertEqual(duplicate.decision, "already_distributed")

    def test_schedule_shortage_does_not_change_quality_decision(self):
        self.assertEqual(self.evaluate().desired_schedule_at, "2026-09-25T19:30:00+09:00")

    def test_registration_failure_can_be_persisted_without_claiming_success(self):
        record = self.evaluate()
        payload = record.__dict__ | {"post_status": "reservation_failed", "metricool_post_id": None}
        self.assertIsNone(json.loads(json.dumps(payload))["metricool_post_id"])

    def test_reconciliation_mismatch_is_not_published(self):
        record = self.evaluate()
        record.post_status = "reconciliation_mismatch"
        self.assertNotEqual(record.post_status, "published")

    def test_editorial_plan_rejects_too_close_slots(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = Path(directory) / "plan.json"
            plan.write_text(json.dumps({"posts": [
                {"article_id": "one", "scheduled_at": "2026-10-01T19:30:00+09:00"},
                {"article_id": "two", "scheduled_at": "2026-10-02T19:30:00+09:00"},
            ]}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "at least 48 hours"):
                selector.load_plan(plan)

    def test_editorial_plan_accepts_three_day_cadence(self):
        plan = selector.load_plan(ROOT / "data/facebook-editorial-plan.json")
        self.assertEqual(len(plan), 8)

    def test_every_planned_article_passes_reader_value_gate(self):
        plan = selector.load_plan(ROOT / "data/facebook-editorial-plan.json")
        records = {
            article_id: selector.evaluate(
                ROOT / "src/content/articles" / f"{article_id}.md", {}, scheduled_at
            )
            for article_id, scheduled_at in plan.items()
        }
        rejected = {
            article_id: record.decision_reason
            for article_id, record in records.items()
            if record.decision != "candidate_selected"
        }
        self.assertEqual(rejected, {})


if __name__ == "__main__":
    unittest.main()
