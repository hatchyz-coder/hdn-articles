#!/usr/bin/env python3
"""Select one high-value candidate while keeping final article quality as a separate gate."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
LATEST_PATH = ROOT / "data" / "candidates" / "latest.json"
OPPORTUNITIES_PATH = ROOT / "data" / "opportunities" / "latest.json"
ARTICLE_DIR = ROOT / "src" / "content" / "articles"
EN_ARTICLE_DIR = ROOT / "src" / "content" / "articles-en"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-score", type=int, default=55, help="candidate-priority floor only; final article quality is gated separately")
    parser.add_argument("--exclude-file", type=Path)
    return parser.parse_args()


def existing_source_urls() -> set[str]:
    urls: set[str] = set()
    source_pattern = re.compile(r'^sourceUrl:\s*["\']?([^"\'\n]+)', re.MULTILINE)
    published_pattern = re.compile(r'(?m)^draft:\s*false\s*$')
    for path in ARTICLE_DIR.glob("*.md") if ARTICLE_DIR.exists() else []:
        text = path.read_text(encoding="utf-8")
        if not published_pattern.search(text):
            continue
        match = source_pattern.search(text)
        if match:
            urls.add(match.group(1).strip())
    return urls


def excluded_urls(path: Path | None) -> set[str]:
    if not path or not path.exists():
        return set()
    return {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip().startswith(("http://", "https://"))}


def valid_slug(value: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value))


def fallback_slug(candidate: dict) -> str:
    candidate_id = str(candidate.get("id", "candidate"))[:12].lower()
    candidate_id = re.sub(r"[^a-z0-9]+", "-", candidate_id).strip("-") or "candidate"
    return f"medical-update-{candidate_id}"


def allocate_unique_slug(candidate: dict) -> str:
    suggested = str(candidate.get("suggested_slug", "")).strip().lower()
    base = suggested if valid_slug(suggested) else fallback_slug(candidate)
    identity = str(candidate.get("id") or candidate.get("url") or base)
    suffix = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:8]
    for slug in [base, f"{base}-{suffix}", *[f"{base}-{suffix}-{i}" for i in range(2, 1000)]]:
        if not (ARTICLE_DIR / f"{slug}.md").exists() and not (EN_ARTICLE_DIR / f"{slug}.md").exists():
            return slug
    raise RuntimeError("Could not allocate a unique slug without overwriting existing articles")


def write_output(name: str, value: str) -> None:
    value = str(value).replace("\r", " ").replace("\n", " ")
    output_path = os.getenv("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as handle:
            handle.write(f"{name}={value}\n")
    else:
        print(f"{name}={value}")


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_ranked_candidates() -> tuple[list[dict], str]:
    opportunity_payload = _load(OPPORTUNITIES_PATH)
    candidate_payload = _load(LATEST_PATH)
    opportunities = opportunity_payload.get("opportunities", [])
    candidates = candidate_payload.get("candidates", [])
    opp_time = str(opportunity_payload.get("generated_at", ""))
    cand_time = str(candidate_payload.get("generated_at", ""))
    if opportunities and (not candidates or opp_time >= cand_time):
        return opportunities, "opportunity"
    if candidates:
        return candidates, "candidate_queue"
    return [], "missing"


def candidate_score(candidate: dict, mode: str) -> int:
    if mode == "opportunity":
        return int(candidate.get("total_score", 0) or 0)
    return int(candidate.get("ai_score", candidate.get("score", 0)) or 0)


def is_article_candidate(candidate: dict, mode: str) -> bool:
    if mode != "opportunity":
        return True
    return str(candidate.get("recommended_action", "")).strip() == "article"


def main() -> int:
    args = parse_args()
    candidates, mode = load_ranked_candidates()
    if not candidates:
        write_output("selected", "false")
        write_output("reason", "candidate queue does not exist")
        return 0
    blocked_urls = existing_source_urls() | excluded_urls(args.exclude_file)
    considered = 0
    for candidate in candidates:
        considered += 1
        url = str(candidate.get("url", "")).strip()
        score = candidate_score(candidate, mode)
        parsed = urlparse(url)
        if score < args.min_score or not is_article_candidate(candidate, mode):
            continue
        if not url or parsed.scheme not in {"http", "https"} or parsed.path.lower().endswith(".pdf") or url in blocked_urls:
            continue
        category = str(candidate.get("suggested_category", "医療経営")).strip() or "医療経営"
        cta = str(candidate.get("recommended_cta") or candidate.get("suggested_cta", "consultation")).strip()
        if cta not in {"consultation", "lhub", "self-pay", "sns"}:
            cta = "consultation"
        slug = allocate_unique_slug(candidate)
        rationale = str(candidate.get("rationale") or candidate.get("reason", "")).replace("\n", " ")
        write_output("selected", "true")
        write_output("url", url)
        write_output("slug", slug)
        write_output("category", category)
        write_output("cta", cta)
        write_output("score", str(score))
        write_output("title", str(candidate.get("title", "")))
        write_output("reason", rationale)
        write_output("selection_mode", mode)
        write_output("considered", str(considered))
        return 0
    write_output("selected", "false")
    write_output("reason", f"no eligible candidate after {mode} prioritization")
    write_output("selection_mode", mode)
    write_output("considered", str(considered))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
