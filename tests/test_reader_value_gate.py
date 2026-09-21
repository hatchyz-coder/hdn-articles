import tempfile
import unittest
from pathlib import Path
from scripts.reader_value_gate import validate_pair

def article(lang="ja", source=True):
    body = ("具体的な判断材料と実務上の注意点を比較し、根拠と適用条件を説明します。" if lang == "ja" else "This section explains practical decisions, limitations, and concrete evidence for readers. ") * 35
    ref = "\nhttps://www.who.int/news\n" if source else ""
    return "---\ntitle: Reader value and operational decisions\ndescription: Practical guidance for readers\npublishedAt: 2026-09-21\ndraft: false\n---\n## Context\n" + body + "\n## Evidence\n" + body + ref

class ReaderValueGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.jp = Path(self.temp.name) / "test.md"
        self.en = Path(self.temp.name) / "en" / "test.md"
        self.en.parent.mkdir()
        self.jp.write_text(article(), encoding="utf-8")
        self.en.write_text(article("en"), encoding="utf-8")
    def test_valid_pair(self):
        self.assertEqual(validate_pair(self.jp, self.en), [])
    def test_missing_source_blocks(self):
        self.en.write_text(article("en", False), encoding="utf-8")
        self.assertTrue(any("source" in x for x in validate_pair(self.jp, self.en)))
    def test_missing_english_blocks(self):
        self.en.unlink()
        self.assertTrue(validate_pair(self.jp, self.en))
    def test_placeholder_blocks(self):
        self.jp.write_text(article() + "\nTODO", encoding="utf-8")
        self.assertTrue(any("placeholder" in x for x in validate_pair(self.jp, self.en)))
    def test_short_body_blocks(self):
        self.jp.write_text("---\ntitle: A sufficiently informative title\ndescription: Brief\npublishedAt: 2026-09-21\ndraft: false\n---\nshort", encoding="utf-8")
        self.assertTrue(any("insufficient" in x for x in validate_pair(self.jp, self.en)))
if __name__ == "__main__":
    unittest.main()
