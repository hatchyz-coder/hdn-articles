import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

if "requests" not in sys.modules:
    requests_stub = types.ModuleType("requests")
    requests_stub.Timeout = TimeoutError
    sys.modules["requests"] = requests_stub

import generate_from_drive_editorial as editorial


class DriveEditorialQualityTests(unittest.TestCase):
    def test_public_contact_does_not_veto_whole_article(self):
        data = {
            "body_markdown": "問い合わせ例: person@example.com / 03-1234-5678",
            "social_x": "contact person@example.com",
        }
        flags = editorial.validate_sanitized_output(data)
        self.assertEqual(flags, [])
        self.assertNotIn("person@example.com", data["body_markdown"])
        self.assertNotIn("03-1234-5678", data["body_markdown"])

    def test_public_sensitive_values_are_removed_before_hard_gate(self):
        data = {
            "body_markdown": "患者ID: ABC123 APIキー: secret-token",
        }
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


if __name__ == "__main__":
    unittest.main()
