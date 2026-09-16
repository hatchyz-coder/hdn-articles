#!/usr/bin/env python3
"""Validate a World Frictions canonical article and its distribution bundle."""
from __future__ import annotations
import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTICLE_DIR = ROOT / "src" / "content" / "articles"
EN_ARTICLE_DIR = ROOT / "src" / "content" / "articles-en"
SOCIAL_DIR = ROOT / "social"
DERIVATIVE_FILES = ("note.md", "linkedin-newsletter.md", "linkedin.md", "facebook.md", "x.md", "reposts.md")
SOURCE_HEADINGS = ("## 出典・一次情報・参考文献", "## 出典・一次情報", "## 参考文献")
FACEBOOK_MIN_CHARS = 1200
FACEBOOK_MAX_CHARS = 1500


def parse_args():
    p = argparse.ArgumentParser(); p.add_argument("--slug", required=True); p.add_argument("--phase", choices=("draft", "final"), default="draft"); return p.parse_args()


def frontmatter(text):
    m = re.match(r"\A---\s*\n(.*?)\n---\s*\n", text, flags=re.S)
    if not m: raise ValueError("Article must start with YAML frontmatter")
    return m.group(1)


def require_metadata(fm):
    for key, value in {"section":"world-frictions","series":"world-frictions","cta":"editorial"}.items():
        if not re.search(rf"(?m)^{re.escape(key)}:\s*[\"']?{re.escape(value)}[\"']?\s*$", fm): raise ValueError(f"Missing required metadata: {key}: {value}")
    if not re.search(r"(?ms)^audiences:\s*\n(?:\s+-\s+.*\n)*\s+-\s+[\"']?general[\"']?\s*$", fm) and not re.search(r"(?m)^audiences:\s*\[.*\bgeneral\b.*\]\s*$", fm): raise ValueError("World Frictions audiences must include general")
    if not re.search(r"(?m)^contentType:\s*[\"']?(news-analysis|opinion|case-study|practical-guide|regulation)[\"']?\s*$", fm): raise ValueError("World Frictions contentType is missing or invalid")


def canonical_url(slug): return f"https://article.hdnjapan.com/articles/{slug}/"


def validate_article(slug):
    jp = ARTICLE_DIR / f"{slug}.md"; en = EN_ARTICLE_DIR / f"{slug}.md"
    if not jp.exists(): raise FileNotFoundError(f"Canonical article not found: {jp}")
    if not en.exists(): raise FileNotFoundError(f"Published JP article has no EN pair: {slug}")
    text = jp.read_text(encoding="utf-8"); require_metadata(frontmatter(text)); require_metadata(frontmatter(en.read_text(encoding="utf-8")))
    if "*" in text: raise ValueError("Markdown asterisk emphasis is not allowed in the canonical article")
    if not any(h in text for h in SOURCE_HEADINGS): raise ValueError("Canonical article must include a source/reference section")
    if "http://" not in text and "https://" not in text: raise ValueError("Canonical article source section must contain at least one URL")
    return [jp, en]


def validate_derivatives(slug, phase):
    base = SOCIAL_DIR / slug
    missing = [name for name in DERIVATIVE_FILES if not (base / name).exists()]
    if missing: raise FileNotFoundError("Missing distribution files: " + ", ".join(missing))
    url = canonical_url(slug); checked = []
    for name in DERIVATIVE_FILES:
        path = base / name; text = path.read_text(encoding="utf-8").strip()
        if not text: raise ValueError(f"Distribution file is empty: {path}")
        if "*" in text: raise ValueError(f"Markdown asterisk emphasis is not allowed: {path}")
        if phase == "final" and name != "reposts.md" and url not in text: raise ValueError(f"Final distribution file must link back to canonical article: {path}")
        if phase == "final" and name == "facebook.md":
            count = len(text)
            if not FACEBOOK_MIN_CHARS <= count <= FACEBOOK_MAX_CHARS: raise ValueError(f"Facebook copy must be {FACEBOOK_MIN_CHARS}-{FACEBOOK_MAX_CHARS} characters; got {count}")
            if not text.startswith("【"): raise ValueError("Facebook copy must begin with a Japanese title in 【】")
        checked.append(path)
    reposts = (base / "reposts.md").read_text(encoding="utf-8")
    if len([line for line in reposts.splitlines() if line.strip().startswith(("- ","1. ","2. ","3. "))]) < 3: raise ValueError("reposts.md must contain at least three repost angles")
    return checked


def validate_bundle(slug, phase="draft"):
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug): raise ValueError("slug must contain lowercase letters, numbers, and hyphens only")
    return [*validate_article(slug), *validate_derivatives(slug, phase)]


def main():
    args = parse_args()
    for path in validate_bundle(args.slug, args.phase): print(path.relative_to(ROOT))
    return 0

if __name__ == "__main__": raise SystemExit(main())
