#!/usr/bin/env python3
"""Fail-closed, deterministic reader-value prepublication checks for paired articles.

This gate checks observable editorial signals, not the truth of claims. Human or
independent source verification remains necessary for high-stakes assertions.
"""
from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

MIN_BODY_CHARS = {"ja": 700, "en": 900}
PLACEHOLDERS = re.compile(r"(?i)\b(?:TODO|TBD|lorem ipsum|insert (?:source|link|text)|example\.com)\b|要確認|仮置き|ここに(?:記入|入力)")
URL = re.compile(r"https?://[^\s)<>\]]+")
PRIVATE = re.compile(r"(?i)(?:drive\.google\.com/(?:file|drive)|docs\.google\.com/document|(?:api[_-]?key|secret|password)\s*[:=])")
MEDICAL = re.compile(r"(?i)\b(?:diagnos(?:is|e)|treat(?:ment)?|prescri(?:be|ption)|dosage|clinical trial)\b|診断|治療|処方|投与|臨床試験")
CLAIM = re.compile(r"\d+(?:\.\d+)?\s*(?:%|％|人|件|円|倍|mg|kg|years?|年|億|万)")
SECTION = re.compile(r"(?m)^#{2,3}\s+\S")
def inspect(path: Path, lang: str) -> list[str]:
    errors = []
    if not path.is_file():
        return [f"{path}: missing article"]
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        return [f"{path}: missing YAML front matter"]
    front, body = text[4:].split("\n---\n", 1)
    for field in ("title", "description", "publishedAt", "draft"):
        if not re.search(rf"(?m)^{field}:\s*\S", front):
            errors.append(f"{path}: missing {field}")
    title = re.search(r"(?m)^title:\s*(.+)", front)
    if title and len(title.group(1).strip().strip('"\'')) < 12:
        errors.append(f"{path}: uninformative title")
    if len(re.sub(r"\s+", "", body)) < MIN_BODY_CHARS[lang]:
        errors.append(f"{path}: insufficient substantive body")
    if len(SECTION.findall(body)) < 2:
        errors.append(f"{path}: insufficient structured explanation")
    if PLACEHOLDERS.search(text):
        errors.append(f"{path}: unresolved placeholder")
    if PRIVATE.search(text):
        errors.append(f"{path}: possible private data or credential")
    links = [u.rstrip(".,;") for u in URL.findall(body)]
    # URL presence is a structural signal only: it cannot establish that a source
    # exists, is relevant to a claim, or supports the article's conclusions.
    excluded_hosts = {"article.hdnjapan.com", "hdnjapan.com", "www.hdnjapan.com",
                      "example.com", "example.org", "example.net", "localhost"}
    sources = []
    for link in links:
        parsed = urlparse(link)
        host = (parsed.hostname or "").lower().rstrip(".")
        if parsed.scheme == "https" and host and host not in excluded_hosts and not host.endswith(".example") and not host.endswith(".invalid") and not host.endswith(".test"):
            sources.append(link)
    if not sources:
        errors.append(f"{path}: no independently accessible external source URL")
    if MEDICAL.search(body) and not sources:
        errors.append(f"{path}: medical claim requires independently checkable sources")
    if CLAIM.search(body) and not sources:
        errors.append(f"{path}: quantitative claim without independently checkable source")
    return errors
def validate_pair(jp: Path, en: Path) -> list[str]:
    errors = inspect(jp, "ja") + inspect(en, "en")
    if jp.stem != en.stem:
        errors.append("Japanese and English article slugs differ")
    return errors
def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jp", type=Path, required=True)
    parser.add_argument("--en", type=Path, required=True)
    args = parser.parse_args(argv)
    errors = validate_pair(args.jp, args.en)
    for error in errors:
        print("READER_VALUE_GATE: " + error, file=sys.stderr)
    if errors:
        print(f"READER_VALUE_GATE: BLOCKED ({len(errors)} issues)", file=sys.stderr)
        return 1
    print("READER_VALUE_GATE: structural checks passed; factual verification is not implied")
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
