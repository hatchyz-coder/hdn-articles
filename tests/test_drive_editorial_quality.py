import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import generate_from_drive_editorial as editorial


class DriveEditorialQualityTests(unittest.TestCase):
    def test_public_contact_does_not_veto_whole_article(self):
        data = {"body_markdown": "問い合わせ例: person@example.com / 03-1234-5678", "social_x": "contact person@example.com"}
        flags = editorial.validate_sanitized_output(data)
        self.assertEqual(flags, [])
        self.assertNotIn("person@example.com", data["body_markdown"])
        self.assertNotIn("03-1234-5678", data["body_markdown"])

    def test_public_sensitive_values_are_removed_before_hard_gate(self):
        data = {"body_markdown": "患者ID: ABC123 APIキー: secret-token"}
        flags = editorial.validate_sanitized_output(data)
        self.assertEqual(flags, [])
        self.assertNotIn("ABC123", data["body_markdown"])
        self.assertNotIn("secret-token", data["body_markdown"])

    def test_generic_private_marker_phrase_is_not_an_article_veto(self):
        data = {"body_markdown": "社外秘情報をLINEへ貼り付けない運用ルールを決める。"}
        self.assertEqual(editorial.validate_sanitized_output(data), [])

    def test_prompt_requires_final_article_scoring_and_reader_value(self):
        prompt = (ROOT / "prompts" / "drive-editorial-daily.md").read_text(encoding="utf-8")
        self.assertIn("FINAL EDITED ARTICLE", prompt)
        self.assertIn("internal rewrite pass", prompt)
        self.assertIn("interesting enough to finish", prompt)
        self.assertIn("failure pattern", prompt)
        self.assertIn("hypothetical", prompt)

    def test_prompt_prevents_lhub_advertorial_repetition_and_unverified_features(self):
        prompt = (ROOT / "prompts" / "drive-editorial-daily.md").read_text(encoding="utf-8")
        self.assertIn("LHub articles must read like editorial, not sales collateral", prompt)
        self.assertIn("Do not write another generic", prompt)
        self.assertIn("must be supported by current public HDN/LHub information", prompt)
        self.assertIn("should stand on its own even for a reader who does not buy LHub", prompt)
        self.assertIn("朗報", prompt)
        self.assertIn("革命", prompt)

    def test_canonical_processor_version_and_hard_floor(self):
        self.assertGreaterEqual(editorial.PROCESSOR_VERSION, 4)
        self.assertEqual(editorial.HARD_MIN_SCORE, 72)

    def test_canonical_main_clamps_score_floor(self):
        source = (ROOT / "scripts" / "generate_from_drive_editorial.py").read_text(encoding="utf-8")
        self.assertIn("args.min_score = max(HARD_MIN_SCORE, int(args.min_score))", source)

    def test_description_repairs_short_japanese_metadata(self):
        text = editorial._description("短い説明", "患者導線の実務記事", 160)
        self.assertGreaterEqual(len(text), 60)
        self.assertLessEqual(len(text), 160)

    def test_description_repairs_short_english_metadata(self):
        text = editorial._description("Short", "Patient journey operations", 180)
        self.assertGreaterEqual(len(text), 50)
        self.assertLessEqual(len(text), 180)

    def test_depth_check_detects_thin_jp_and_en_pair(self):
        data = {"title": "JP", "summary": "summary", "body_markdown": "## A\nshort\n## B\nshort", "english_title": "EN", "english_summary": "summary", "english_body_markdown": "## A\nshort\n## B\nshort"}
        issues = editorial._depth_issues(data)
        self.assertIn("jp_body_too_thin", issues)
        self.assertIn("en_body_too_thin", issues)

    def test_depth_check_accepts_substantive_pair(self):
        data = {
            "title": "JP", "summary": "summary",
            "body_markdown": "## A\n" + ("具体的な運用判断。" * 100) + "\n## B\n" + ("失敗パターンと改善。" * 60),
            "english_title": "EN", "english_summary": "summary",
            "english_body_markdown": "## A\n" + ("Operational detail and trade-offs. " * 35) + "\n## B\n" + ("Failure patterns and decisions. " * 30),
        }
        self.assertEqual(editorial._depth_issues(data), [])

    def test_drive_identifiers_are_not_emitted_as_public_step_outputs(self):
        source = (ROOT / "scripts" / "generate_from_drive_editorial.py").read_text(encoding="utf-8")
        self.assertNotIn('base.write_output("file_id"', source)
        self.assertNotIn('base.write_output("source_url"', source)
        self.assertNotIn('base.write_output("source_name"', source)
        self.assertIn('selectedDocumentKey', source)


if __name__ == "__main__":
    unittest.main()
