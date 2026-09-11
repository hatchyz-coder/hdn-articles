from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
JP_DIR = ROOT / "src/content/articles"
EN_DIR = ROOT / "src/content/articles-en"
REQUIRED_FIELDS = ("audiences", "section", "industry", "series", "contentType")


def frontmatter(text: str) -> str:
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise AssertionError("missing frontmatter")
    return parts[1]


def scalar_value(block: str, key: str) -> str | None:
    match = re.search(rf'(?m)^{re.escape(key)}:\s*["\']?([^"\'\n]+)', block)
    return match.group(1).strip() if match else None


def audiences(block: str) -> list[str]:
    lines = block.splitlines()
    values: list[str] = []
    for index, line in enumerate(lines):
        if line.strip() != "audiences:":
            continue
        for child in lines[index + 1 :]:
            match = re.match(r'^\s+-\s+["\']?([^"\'\n]+)', child)
            if not match:
                break
            values.append(match.group(1).strip())
        break
    return values


class ArticleMetadataContractTests(unittest.TestCase):
    def test_all_published_japanese_articles_have_explicit_metadata(self):
        missing: dict[str, list[str]] = {}
        for path in sorted(JP_DIR.glob("*.md")):
            block = frontmatter(path.read_text(encoding="utf-8"))
            if not re.search(r"(?m)^draft:\s*false\s*$", block):
                continue
            absent = [field for field in REQUIRED_FIELDS if not re.search(rf"(?m)^{field}:", block)]
            if absent:
                missing[path.name] = absent
        self.assertEqual({}, missing)

    def test_english_pairs_match_japanese_taxonomy(self):
        mismatches: list[str] = []
        for en_path in sorted(EN_DIR.glob("*.md")):
            jp_path = JP_DIR / en_path.name
            if not jp_path.exists():
                continue
            jp = frontmatter(jp_path.read_text(encoding="utf-8"))
            en = frontmatter(en_path.read_text(encoding="utf-8"))
            if audiences(jp) != audiences(en):
                mismatches.append(f"{en_path.name}: audiences")
            for key in ("section", "industry", "series", "contentType"):
                if scalar_value(jp, key) != scalar_value(en, key):
                    mismatches.append(f"{en_path.name}: {key}")
        self.assertEqual([], mismatches)

    def test_nonmedical_lhub_articles_never_enter_clinic_lane(self):
        violations: list[str] = []
        for path in sorted(JP_DIR.glob("*.md")):
            block = frontmatter(path.read_text(encoding="utf-8"))
            if scalar_value(block, "section") != "lhub-usecase":
                continue
            if scalar_value(block, "industry") in {"medical", "dental"}:
                continue
            if "clinic" in audiences(block):
                violations.append(path.name)
        self.assertEqual([], violations)

    def test_world_frictions_requires_editorial_cta(self):
        violations: list[str] = []
        for directory in (JP_DIR, EN_DIR):
            for path in sorted(directory.glob("*.md")):
                block = frontmatter(path.read_text(encoding="utf-8"))
                if scalar_value(block, "section") == "world-frictions":
                    if scalar_value(block, "cta") != "editorial":
                        violations.append(str(path.relative_to(ROOT)))
        self.assertEqual([], violations)


if __name__ == "__main__":
    unittest.main()
