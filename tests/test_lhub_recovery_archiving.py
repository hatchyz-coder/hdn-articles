import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import audit_lhub_daily as audit
import archive_published_drive_seed as archive

class RecoveryTests(unittest.TestCase):
    def test_archive_disallows_source_target_same(self):
        with self.assertRaises(ValueError):
            archive.publication_urls("../unsafe")

    def test_archive_urls_complete(self):
        self.assertEqual(len(archive.publication_urls("example-slug")), 4)

    def test_archive_gets_all_sites(self):
        self.assertTrue(archive.publication_urls("x")[1].startswith("https://article.hdnjapan.com/en/"))

    def test_archive_parent_already_done(self):
        drive = Mock()
        drive.files.return_value.get.return_value.execute.return_value = {
            "mimeType": "application/vnd.google-apps.document", "parents": ["archive"]}
        self.assertEqual(archive.archive_file(drive, "doc", "source", "archive"), "already_archived")
        drive.files.return_value.update.assert_not_called()

    def test_archive_rejects_unknown_parent(self):
        drive = Mock()
        drive.files.return_value.get.return_value.execute.return_value = {
            "mimeType": "application/vnd.google-apps.document", "parents": ["unrelated"]}
        with self.assertRaises(ValueError):
            archive.archive_file(drive, "doc", "source", "archive")

    def test_audit_finds_gap(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            jp = root / "src/content/articles"
            jp.mkdir(parents=True)
            (jp / "item.md").write_text("---\npublishedAt: 2026-11-01\ndraft: false\nsection: lhub-usecase\n---\ntext", encoding="utf8")
            from datetime import date
            result = audit.audit(root, date(2026, 11, 1), date(2026, 11, 2))
            self.assertEqual(result["missing_days"], ["2026-11-02"])

    def test_reserve_excludes_existing_article(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reserve = root / "fallback"
            reserve.mkdir()
            (reserve / "one.json").write_text(json.dumps({"slug": "one"}))
            jp = root / "jp"; jp.mkdir()
            en = root / "en"; en.mkdir()
            (jp / "one.md").write_text("")
            self.assertEqual(audit.reserve_inventory(reserve, {}, jp, en)["remaining"], 0)


    def test_recovery_preflight_verification_is_valid_shell(self):
        import subprocess
        workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/daily-drive-editorial-fallback.yml").read_text(encoding="utf-8")
        marker = "          git fetch origin main\\n"
        self.assertIn(marker, workflow)
        shell = workflow.split(marker, 1)[1]
        # The publish-check command must not swallow the summary redirect into
        # a quoted grep pattern, as that makes recovery always report failure.
        self.assertIn("grep -q '^published=true
    unittest.main()
", shell)
        self.assertIn("GITHUB_OUTPUT= python scripts/lhub_daily_preflight.py", shell)
        self.assertNotIn("grep -q '^published=true >>", shell)
        extracted = "\\n".join(line[10:] if line.startswith("          ") else "" for line in shell.splitlines())
        subprocess.run(["bash", "-n"], input=extracted, text=True, check=True)

if __name__ == "__main__":
    unittest.main()
