#!/usr/bin/env python3
"""Validate a World Frictions canonical article and its distribution bundle."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTICLE_DIR = ROOT / "src" / "content" / "articles"
SOCIAL_DIR = ROOT / "social"

DERIVATIVE_FILES = (
    "note.md",
    "linkedin-newsletter.md",
    "linkedin.md",
    "facebook.md",
    "x.md",
    "reposts.md",
)

SOURCE_HEADINGS = (
    "## 出典・一次情報・参考文献",
    "## 出典・一次情報",
    "## 参考文献",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug", required=True)
    parser.add_argument("--phase", choices=("draft", "final"), default="draft")
    return parser.parse_args()


def frontmatter(text: str) -> str:
    match = re.match(r"\A---\s*\n(.*?)\n---\s*\n", text, flags=re.S)
    if not match:
        raise ValueError("Article must start with YAML frontmatter")
    return match.group(1)


def require_metadata(fm: str) -> None:
    required_scalars = {
        "section": "world-frictions",
        "series": "world-frictions",
        "cta": "editorial",
    }
    for key, value in required_scalars.items():
        if not re.search(rf"(?m)^{re.escape(key)}:\s*{re.escape(value)}\s*$", fm):
            raise ValueError(f"Missing required metadata: {key}: {value}")

    if not re.search(r"(?ms)^audiences:\s*\n(?:\s+-\s+.*\n)*\s+-\s+general\s*$", fm):
        if not re.search(r"(?m)^audiences:\s*\[.*\bgeneral\b.*\]\s*$", fm):
            raise ValueError("World Frictions audiences must include general")

    if not re.search(
        r"(?m)^contentType:\s*(news-analysis|opinion|case-study|practical-guide|regulation)\s*$",
        fm,
    ):
        raise ValueError("World Frictions contentType is missing or invalid")


def canonical_url(slug: str) -> str:
    return f"https://article.hdnjapan.com/articles/{slug}/"


def validate_article(slug: str) -> Path:
    path = ARTICLE_DIR / f"{slug}.md"
    if not path.exists():
        raise FileNotFoundError(f"Canonical article not found: {path}")

    text = path.read_text(encoding="utf-8")
    require_metadata(frontmatter(text))

    if "**" in text:
        raise ValueError("Markdown asterisk emphasis is not allowed in the canonical article")
    if not any(heading in text for heading in SOURCE_HEADINGS):
        raise ValueError("Canonical article must include a source/reference section")
    if "http://" not in text and "https://" not in text:
        raise ValueError("Canonical article source section must contain at least one URL")
    return path


def validate_derivatives(slug: str, phase: str) -> list[Path]:
    base = SOCIAL_DIR / slug
    missing = [name for name in DERIVATIVE_FILES if not (base / name).exists()]
    if missing:
        raise FileNotFoundError("Missing distribution files: " + ", ".join(missing))

    url = canonical_url(slug)
    checked: list[Path] = []
    for name in DERIVATIVE_FILES:
        path = base / name
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            raise ValueError(f"Distribution file is empty: {path}")
        if "**" in text:
            raise ValueError(f"Markdown asterisk emphasis is not allowed: {path}")
        if phase == "final" and name != "reposts.md" and url not in text:
            raise ValueError(f"Final distribution file must link back to canonical article: {path}")
        checked.append(path)

    reposts = (base / "reposts.md").read_text(encoding="utf-8")
    candidates = [line for line in reposts.splitlines() if line.strip().startswith(("- ", "1. ", "2. ", "3. "))]
    if len(candidates) < 3:
        raise ValueError("reposts.md must contain at least three repost angles")
    return checked


def validate_bundle(slug: str, phase: str = "draft") -> list[Path]:
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        raise ValueError("slug must contain lowercase letters, numbers, and hyphens only")
    article = validate_article(slug)
    return [article, *validate_derivatives(slug, phase)]


def main() -> int:
    args = parse_args()
    for path in validate_bundle(args.slug, args.phase):
        print(path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
