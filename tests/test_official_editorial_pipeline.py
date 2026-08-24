import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import build_opportunity_report as opportunity
import collect_official_sources as collector
import collect_official_sources_fair as fair_collector
import generate_content
import prepare_official_editorial_queue as queue
import select_top_candidate as selector
import update_official_candidate_state as candidate_state


class OfficialEditorialPipelineTests(unittest.TestCase):
    def test_fair_collector_cannot_stop_after_first_five_sources(self):
        config = (ROOT / "config" / "official-sources.yaml").read_text(encoding="utf-8")
        source_count = config.count("\n  - id:")
        self.assertGreaterEqual(source_count, 20)
        self.assertEqual(collector.MAX_PER_SOURCE, 5)
        self.assertGreater(collector.MAX_TOTAL, source_count * collector.MAX_PER_SOURCE)
        self.assertEqual(fair_collector.collector.MAX_PER_SOURCE, 5)

    def test_pending_queue_keeps_old_unpublished_candidates(self):
        old = {"url": "https://example.com/old", "title": "Old useful update", "score": 70, "source_id": "a"}
        fresh = {"url": "https://example.com/new", "title": "New useful update", "score": 75, "source_id": "b"}
        merged = queue.merge_pending([old], [fresh], set())
        self.assertEqual({item["url"] for item in merged}, {old["url"], fresh["url"]})

    def test_pending_queue_preserves_failures_and_demotes_repeated_failure(self):
        failed = {"url": "https://example.com/failed", "title": "Failed", "score": 80, "source_id": "a", "generation_failures": 2}
        fresh = {"url": "https://example.com/fresh", "title": "Fresh", "score": 75, "source_id": "b"}
        merged = queue.merge_pending([failed], [fresh], set())
        self.assertEqual(merged[0]["url"], fresh["url"])
        failed_item = next(item for item in merged if item["url"] == failed["url"])
        self.assertEqual(failed_item["generation_failures"], 2)

    def test_opportunity_ranking_keeps_generation_failure_penalty(self):
        candidate = {"generation_failures": 3}
        ranked = opportunity.apply_generation_failure_penalty(candidate, {"total_score": 88, "article_value_score": 90})
        self.assertEqual(ranked["generation_failure_penalty"], 30)
        self.assertEqual(ranked["total_score"], 58)
        self.assertEqual(ranked["article_value_score"], 90)

    def test_candidate_state_failure_is_retryable_and_published_is_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pending.json"
            url = "https://example.com/retry"
            path.write_text(json.dumps({"candidates": [{"url": url, "title": "Retry", "generation_failures": 1}]}), encoding="utf-8")
            with patch.object(sys, "argv", ["update_official_candidate_state.py", "--pending-path", str(path), "--url", url, "--outcome", "generation_failed"]):
                self.assertEqual(candidate_state.main(), 0)
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["candidates"][0]["generation_failures"], 2)
            with patch.object(sys, "argv", ["update_official_candidate_state.py", "--pending-path", str(path), "--url", url, "--outcome", "published"]):
                self.assertEqual(candidate_state.main(), 0)
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["candidates"], [])

    def test_pending_queue_removes_only_published_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            article_dir = Path(tmp)
            (article_dir / "draft.md").write_text('---\nsourceUrl: "https://example.com/draft"\ndraft: true\n---\n', encoding="utf-8")
            (article_dir / "live.md").write_text('---\nsourceUrl: "https://example.com/live"\ndraft: false\n---\n', encoding="utf-8")
            with patch.object(queue, "ARTICLE_DIR", article_dir):
                published = queue.published_source_urls()
            self.assertIn("https://example.com/live", published)
            self.assertNotIn("https://example.com/draft", published)

    def test_selector_does_not_block_source_used_only_by_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            article_dir = Path(tmp)
            (article_dir / "draft.md").write_text('---\nsourceUrl: "https://example.com/draft"\ndraft: true\n---\n', encoding="utf-8")
            (article_dir / "live.md").write_text('---\nsourceUrl: "https://example.com/live"\ndraft: false\n---\n', encoding="utf-8")
            with patch.object(selector, "ARTICLE_DIR", article_dir):
                urls = selector.existing_source_urls()
            self.assertIn("https://example.com/live", urls)
            self.assertNotIn("https://example.com/draft", urls)

    def test_official_final_quality_floor_is_independent_and_72(self):
        self.assertEqual(generate_content.FINAL_QUALITY_FLOOR, 72)
        thin = {
            "title": "JP", "summary": "s", "body_markdown": "## A\nshort\n## B\nshort",
            "english_title": "EN", "english_summary": "s", "english_body_markdown": "## A\nshort\n## B\nshort",
            "should_publish": True, "editorial_score": 90,
        }
        issues = generate_content.final_quality_issues(thin, 72)
        self.assertIn("jp_body_too_thin", issues)
        self.assertIn("en_body_too_thin", issues)

    def test_official_workflow_uses_canonical_20_source_queue_and_no_duplicate_deploy(self):
        text = (ROOT / ".github/workflows/official-source-daily-publish.yml").read_text(encoding="utf-8")
        self.assertIn("prepare_official_editorial_queue.py", text)
        self.assertIn("collect_official_sources_fair.py", text)
        self.assertIn("build_opportunity_report.py", text)
        self.assertIn("update_official_candidate_state.py", text)
        self.assertIn("--outcome generation_failed", text)
        self.assertIn("--outcome published", text)
        self.assertIn("--min-score 72", text)
        self.assertIn("for attempt in 1 2 3 4 5", text)
        self.assertIn("Verify JP and EN production URLs", text)
        self.assertNotIn("gh workflow run deploy-pages.yml --ref main", text)

    def test_official_state_writers_share_one_non_cancelling_lock(self):
        collector_workflow = (ROOT / ".github/workflows/official-source-collector.yml").read_text(encoding="utf-8")
        publisher_workflow = (ROOT / ".github/workflows/official-source-daily-publish.yml").read_text(encoding="utf-8")
        for text in (collector_workflow, publisher_workflow):
            self.assertIn("group: official-sources-state-writer", text)
            self.assertIn("cancel-in-progress: false", text)

    def test_legacy_automatic_article_paths_are_manual_only(self):
        for name in ("drive-knowledge-article-pr.yml", "hdn-growth-pipeline.yml", "discover-article-candidates.yml"):
            text = (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
            self.assertIn("workflow_dispatch:", text)
            self.assertNotIn("schedule:", text, msg=name)


if __name__ == "__main__":
    unittest.main()
