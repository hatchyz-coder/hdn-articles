#!/usr/bin/env python3
"""Lightweight JST preflight for LHub Daily Guarantee.

Runs before dependency setup. It only inspects repository markdown and never
calls external APIs or reads reserve content.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parents[1]
ARTICLE_DIR = ROOT / "src" / "content" / "articles"


def frontmatter_value(markdown: str, key: str) -> str:
    match = re.search(rf'(?m)^{re.escape(key)}:\s*["\']?([^\n"\']+)', markdown)
    return match.group(1).strip() if match else ""


def is_lhub_article(markdown: str) -> bool:
    if frontmatter_value(markdown, "draft").lower() == "true":
        return False
    if frontmatter_value(markdown, "section") == "lhub-usecase":
        return True
    audiences = re.search(r"(?ms)^audiences:\s*\n(?P<body>(?:\s+-.*\n?)+)", markdown)
    return bool(audiences and re.search(r'(?m)^\s+-\s*["\']?lhub["\']?\s*$', audiences.group("body")))


def published_lhub_slugs_for_day(article_dir: Path, day: str) -> list[str]:
    slugs: list[str] = []
    for path in sorted(article_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        if frontmatter_value(text, "publishedAt") == day and is_lhub_article(text):
            slugs.append(path.stem)
    return slugs


def emit(key: str, value: str) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    line = f"{key}={value}"
    if output_path:
        with open(output_path, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    else:
        print(line)


def main() -> int:
    day = datetime.now(JST).date().isoformat()
    published = published_lhub_slugs_for_day(ARTICLE_DIR, day)
    emit("day", day)
    emit("published", "true" if published else "false")
    emit("reason", "already_published_today" if published else "not_published_today")
    emit("published_slug", published[0] if published else "")
    if published:
        print(f"Daily preflight: LHub article already published today: {published[0]}")
    else:
        print("Daily preflight: no LHub article published today; continue to full pipeline")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
