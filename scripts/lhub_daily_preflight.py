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
DAILY_TARGET = 2


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
    count = len(published)
    target_reached = count >= DAILY_TARGET
    emit("day", day)
    emit("published", "true" if target_reached else "false")
    emit("reason", "daily_target_reached" if target_reached else "daily_target_not_reached")
    emit("published_slug", published[-1] if published else "")
    emit("published_count", str(count))
    emit("daily_target", str(DAILY_TARGET))
    emit("remaining", str(max(0, DAILY_TARGET - count)))
    if target_reached:
        print(f"Daily preflight: LHub daily target reached ({count}/{DAILY_TARGET})")
    else:
        print(f"Daily preflight: LHub daily target not reached ({count}/{DAILY_TARGET}); continue")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
