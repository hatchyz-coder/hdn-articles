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


def clean_social_body(text: str) -> str:
    text = text.strip()
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"(?m)^\s*(?:続きはこちら|記事はこちら|詳しくはこちら)[：:]?\s*$", "", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def clean_x_body(text: str) -> str:
    text = clean_social_body(text)
    if len(text) > 210:
        text = text[:207].rstrip("、。,. \n") + "…"
    return text


def finalize_post(path: Path, body: str, article_url: str, label: str) -> Path:
    if not body:
        raise ValueError(f"Social draft became empty after cleanup: {path}")
    path.write_text(f"{body}\n\n{label}\n{article_url}\n", encoding="utf-8")
    return path


def finalize_social_posts(slug: str) -> list[Path]:
    social_path = SOCIAL_DIR / slug
    paths = {
        "x": social_path / "x.md",
        "linkedin": social_path / "linkedin.md",
        "facebook": social_path / "facebook.md",
    }
    for channel, path in paths.items():
        if not path.exists():
            raise FileNotFoundError(f"{channel} draft not found: {path}")

    article_url = f"{PRODUCTION_ORIGIN}/articles/{slug}/"
    finalized = [
        finalize_post(
            paths["x"],
            clean_x_body(paths["x"].read_text(encoding="utf-8")),
            article_url,
            "続きはこちら",
        ),
        finalize_post(
            paths["linkedin"],
            clean_social_body(paths["linkedin"].read_text(encoding="utf-8")),
            article_url,
            "記事はこちら",
        ),
        finalize_post(
            paths["facebook"],
            clean_social_body(paths["facebook"].read_text(encoding="utf-8")),
            article_url,
            "記事はこちら",
        ),
    ]
    return finalized


def main() -> int:
    args = parse_args()
    slug = article_slug(args.article_path)
    for path in finalize_social_posts(slug):
        print(path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
