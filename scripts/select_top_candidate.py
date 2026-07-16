#!/usr/bin/env python3
"""Select one safe, high-value candidate for automatic draft generation."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
LATEST_PATH = ROOT / "data" / "candidates" / "latest.json"
ARTICLE_DIR = ROOT / "src" / "content" / "articles"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-score", type=int, default=70)
    parser.add_argument("--exclude-file", type=Path)
    return parser.parse_args()


def existing_source_urls() -> set[str]:
    urls: set[str] = set()
    if not ARTICLE_DIR.exists():
        return urls
    pattern = re.compile(r'^sourceUrl:\s*["\']?([^"\'\n]+)', re.MULTILINE)
    for path in ARTICLE_DIR.glob("*.md"):
        match = pattern.search(path.read_text(encoding="utf-8"))
        if match:
            urls.add(match.group(1).strip())
    return urls


def excluded_urls(path: Path | None) -> set[str]:
    if not path or not path.exists():
        return set()
    return {
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip().startswith(("http://", "https://"))
    }


def valid_slug(value: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value))


def fallback_slug(candidate: dict) -> str:
    candidate_id = str(candidate.get("id", "candidate"))[:12]
    return f"medical-update-{candidate_id}"


def write_output(name: str, value: str) -> None:
    output_path = os.getenv("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as handle:
            handle.write(f"{name}={value}\n")
    else:
        print(f"{name}={value}")


def main() -> int:
    args = parse_args()
    if not LATEST_PATH.exists():
        write_output("selected", "false")
        write_output("reason", "candidate queue does not exist")
        return 0

    payload = json.loads(LATEST_PATH.read_text(encoding="utf-8"))
    blocked_urls = existing_source_urls() | excluded_urls(args.exclude_file)

    for candidate in payload.get("candidates", []):
        url = str(candidate.get("url", "")).strip()
        score = int(candidate.get("ai_score", 0))
        parsed = urlparse(url)
        if score < args.min_score:
            continue
        if not url or parsed.scheme not in {"http", "https"}:
            continue
        if parsed.path.lower().endswith(".pdf"):
            continue
        if url in blocked_urls:
            continue

        slug = str(candidate.get("suggested_slug", "")).strip().lower()
        if not valid_slug(slug):
            slug = fallback_slug(candidate)

        category = str(candidate.get("suggested_category", "医療経営")).strip() or "医療経営"
        cta = str(candidate.get("suggested_cta", "consultation")).strip()
        if cta not in {"consultation", "lhub", "self-pay"}:
            cta = "consultation"

        write_output("selected", "true")
        write_output("url", url)
        write_output("slug", slug)
        write_output("category", category)
        write_output("cta", cta)
        write_output("score", str(score))
        write_output("title", str(candidate.get("title", "")).replace("\n", " "))
        write_output("reason", str(candidate.get("reason", "")).replace("\n", " "))
        return 0

    write_output("selected", "false")
    write_output("reason", "no eligible candidate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
