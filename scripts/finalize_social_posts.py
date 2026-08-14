#!/usr/bin/env python3
"""Finalize social copy after an article is approved for publication."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOCIAL_DIR = ROOT / "social"
PRODUCTION_ORIGIN = "https://article.hdnjapan.com"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--article-path", required=True)
    return parser.parse_args()


def article_slug(article_path: str) -> str:
    path = Path(article_path)
    if path.suffix != ".md":
        raise ValueError("Article path must be a Markdown file")
    return path.stem


def clean_x_body(text: str) -> str:
    text = text.strip()
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"(?m)^\s*続きはこちら[：:]?\s*$", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) > 210:
        text = text[:207].rstrip("、。,. \n") + "…"
    return text


def finalize_x_post(slug: str) -> Path:
    path = SOCIAL_DIR / slug / "x.md"
    if not path.exists():
        raise FileNotFoundError(f"X draft not found: {path}")

    body = clean_x_body(path.read_text(encoding="utf-8"))
    if not body:
        raise ValueError("X draft became empty after cleanup")

    article_url = f"{PRODUCTION_ORIGIN}/articles/{slug}/"
    final = f"{body}\n\n続きはこちら\n{article_url}\n"
    path.write_text(final, encoding="utf-8")
    return path


def main() -> int:
    args = parse_args()
    slug = article_slug(args.article_path)
    path = finalize_x_post(slug)
    print(path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
