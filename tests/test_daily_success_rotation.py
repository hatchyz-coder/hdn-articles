import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import publication_fact_gate as fact_gate
import run_drive_editorial_resilient as resilient


def article(body: str) -> str:
    filler = "運営導線を整理し、利用者に必要な情報を適切なタイミングで届けることが重要です。\n" * 20
    return f"---\npublishedAt: 2026-09-27\n---\n\n{filler}{body}\n"


class DailySuccessRotationTests(unittest.TestCase):
    def test_deterministic_repair_removes_unsafe_lines_and_passes(self):
        source = article(
            "空き家率は13.8%で過去最高です【0†L318-L336】。\n"
            "LINE の継続課金機能を活用できます。\n"
            "山形県の古民家宿では予約率18%向上。"
        )
        result = fact_gate.repair_markdown(source)
        self.assertTrue(result["accepted"])
        self.assertEqual(len(result["removed_lines"]), 3)
        self.assertTrue(fact_gate.evaluate(result["markdown"])["publication_fact_gate"])

    def test_repair_refuses_to_gut_badly_grounded_article(self):
        source = "---\npublishedAt: 2026-09-27\n---\n\n" + "\n".join(
            ["山形県の古民家宿では予約率18%向上。" for _ in range(8)]
        )
        result = fact_gate.repair_markdown(source)
        self.assertFalse(result["accepted"])
        self.assertGreater(result["removed_ratio"], 0.25)

    def test_fact_gate_failure_is_a_rotation_reason(self):
        retry, reason = resilient.should_continue(
            0, {"selected": False, "reason": "fact_gate_failed"}
        )
        self.assertTrue(retry)
        self.assertEqual(reason, "fact_gate_failed")

    def test_unrepairable_candidate_is_cleaned_and_state_marked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            jp = root / "src/content/articles/test-slug.md"
            en = root / "src/content/articles-en/test-slug.md"
            social = root / "social/test-slug"
            jp.parent.mkdir(parents=True)
            en.parent.mkdir(parents=True)
            social.mkdir(parents=True)
            bad = "---\npublishedAt: 2026-09-27\n---\n\n" + "\n".join(
                ["山形県の古民家宿では予約率18%向上。" for _ in range(8)]
            )
            jp.write_text(bad, encoding="utf-8")
            en.write_text(bad, encoding="utf-8")
            (social / "x.md").write_text("draft", encoding="utf-8")
            state = root / "state.json"
            state.write_text(json.dumps({
                "documents": {"abc": {"status": "generated", "slug": "test-slug"}}
            }), encoding="utf-8")

            old = Path.cwd()
            try:
                import os
                os.chdir(root)
                report, output = resilient.apply_publication_fact_gate(
                    {"selected": True, "slug": "test-slug"},
                    "selected=true\nslug=test-slug\n",
                    ["--state-path", str(state)],
                )
            finally:
                os.chdir(old)

            self.assertFalse(report["selected"])
            self.assertEqual(report["reason"], "fact_gate_failed")
            self.assertIn("selected=false", output)
            self.assertFalse(jp.exists())
            self.assertFalse(en.exists())
            saved = json.loads(state.read_text(encoding="utf-8"))
            self.assertEqual(saved["documents"]["abc"]["status"], "fact_gate_failed")
            self.assertTrue(saved["documents"]["abc"]["manualReview"])


if __name__ == "__main__":
    unittest.main()
