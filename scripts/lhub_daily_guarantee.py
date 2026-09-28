#!/usr/bin/env python3
"""Guarantee at most one LHub article per JST day with an API-independent reserve fallback."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from publication_fact_gate import evaluate

JST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESERVE_DIR = ROOT / "fallback" / "lhub"
ARTICLE_DIR = ROOT / "src" / "content" / "articles"
ENGLISH_DIR = ROOT / "src" / "content" / "articles-en"
SOCIAL_DIR = ROOT / "social"
RESERVE_WARNING_THRESHOLD = 10
RESERVE_CRITICAL_THRESHOLD = 7

FALLBACK_REASONS = {
    "api_rate_limited",
    "api_model_unavailable",
    "api_unconfigured",
    "api_quota_exhausted",
    "no_candidate",
    "fact_gate_failed",
    "generator_error",
    "completed_without_selection",
    "rotation_attempts_exhausted",
    "api_timeout",
    "os_timeout",
    "low_score",
    "duplicate_source",
    "confidential",
    "manual_review_retry_limit",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reserve-dir", type=Path, default=DEFAULT_RESERVE_DIR)
    parser.add_argument("--state-path", type=Path, required=True)
    parser.add_argument("--report-path", type=Path, required=True)
    parser.add_argument("--max-attempts", type=int, default=4)
    parser.add_argument("--backoff-seconds", type=int, default=8)
    parser.add_argument("generator_args", nargs=argparse.REMAINDER)
    return parser.parse_args()


def parse_outputs(text: str) -> dict[str, str]:
    outputs: dict[str, str] = {}
    for line in text.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip():
            outputs[key.strip()] = value.strip()
    return outputs


def emit(outputs: dict[str, Any]) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    lines = [f"{key}={str(value).lower() if isinstance(value, bool) else value}" for key, value in outputs.items()]
    if output_path:
        with open(output_path, "a", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
    else:
        print("\n".join(lines))


def frontmatter_value(markdown: str, key: str) -> str:
    match = re.search(rf"(?m)^{re.escape(key)}:\s*[\"']?([^\n\"']+)", markdown)
    return match.group(1).strip() if match else ""


def is_lhub_article(markdown: str) -> bool:
    if frontmatter_value(markdown, "draft").lower() == "true":
        return False
    if frontmatter_value(markdown, "section") == "lhub-usecase":
        return True
    audiences = re.search(r"(?ms)^audiences:\s*\n(?P<body>(?:\s+-.*\n?)+)", markdown)
    return bool(audiences and re.search(r"(?m)^\s+-\s*[\"']?lhub[\"']?\s*$", audiences.group("body")))


def published_lhub_slugs_for_day(article_dir: Path, day: str) -> list[str]:
    slugs: list[str] = []
    for path in sorted(article_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        if frontmatter_value(text, "publishedAt") == day and is_lhub_article(text):
            slugs.append(path.stem)
    return slugs


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    state["updatedAt"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def body_char_count(markdown: str) -> int:
    body = markdown.split("---", 2)[2] if markdown.startswith("---") and len(markdown.split("---", 2)) == 3 else markdown
    return len(re.sub(r"\s+", "", body))


def build_markdown(data: dict[str, Any], language: str, day: str) -> str:
    if language == "jp":
        title = data["title"]
        description = data["description"]
        category = data.get("category", "LHub活用")
        tags = data.get("tags", ["LHub", "LINE運用", "業務改善"])
        author = "羽田野 剛士"
        summary = data["summary"]
        body = data["body_markdown"]
    else:
        title = data["english_title"]
        description = data["english_description"]
        category = data.get("english_category", "LHub Operations")
        tags = data.get("english_tags", ["LHub", "LINE Operations", "Workflow"])
        author = "Tsuyoshi Hadano"
        summary = data["english_summary"]
        body = data["english_body_markdown"]

    lines = [
        "---",
        f"title: {json.dumps(title, ensure_ascii=False)}",
        f"description: {json.dumps(description, ensure_ascii=False)}",
        f"publishedAt: {day}",
        f"updatedAt: {day}",
        f"category: {json.dumps(category, ensure_ascii=False)}",
        "tags:",
        *[f"  - {json.dumps(str(tag), ensure_ascii=False)}" for tag in tags],
        f"author: {json.dumps(author, ensure_ascii=False)}",
        "draft: false",
        "featured: false",
        'cta: "lhub"',
        "audiences:",
        '  - "lhub"',
        'section: "lhub-usecase"',
        f'industry: "{data.get("industry", "other")}"',
        'series: "lhub-use-cases"',
        'contentType: "practical-guide"',
        "---",
        "",
        summary.strip(),
        "",
        body.strip(),
        "",
    ]
    return "\n".join(lines)


def validate_reserve(data: dict[str, Any], day: str) -> tuple[str, str]:
    required = {
        "slug", "title", "description", "summary", "body_markdown",
        "english_title", "english_description", "english_summary", "english_body_markdown",
        "social_x", "social_linkedin", "social_facebook",
    }
    missing = sorted(required - set(data))
    if missing:
        raise ValueError(f"reserve missing fields: {', '.join(missing)}")

    jp = build_markdown(data, "jp", day)
    en = build_markdown(data, "en", day)
    chars = body_char_count(jp)
    if not 2000 <= chars <= 3000:
        raise ValueError(f"{data['slug']}: Japanese article must be 2000-3000 characters, got {chars}")
    for label, article in (("JP", jp), ("EN", en)):
        result = evaluate(article)
        if not result["publication_fact_gate"]:
            raise ValueError(f"{data['slug']}: {label} Fact Gate failed: {result['reason']}")

    facebook = str(data["social_facebook"]).strip()
    linkedin = str(data["social_linkedin"]).strip()
    x = str(data["social_x"]).strip()
    if not x.startswith("【"):
        raise ValueError(f"{data['slug']}: X draft must start with 【")
    if not facebook.startswith("【") or not 1200 <= len(facebook) <= 1400:
        raise ValueError(f"{data['slug']}: Facebook draft must be 1200-1400 characters before URL finalization")
    if not linkedin.startswith("【") or " / " not in linkedin.splitlines()[0] or "English follows below." not in linkedin:
        raise ValueError(f"{data['slug']}: LinkedIn draft must use bilingual contract")
    if len(linkedin) > 2900:
        raise ValueError(f"{data['slug']}: LinkedIn draft too long")
    return jp, en


def unused_reserve_slugs(reserve_dir: Path, state: dict[str, Any]) -> list[str]:
    used = state.get("fallbackReserves", {})
    slugs: list[str] = []
    for path in sorted(reserve_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        slug = str(data.get("slug", "")).strip()
        if not slug or slug in used:
            continue
        if (ARTICLE_DIR / f"{slug}.md").exists() or (ENGLISH_DIR / f"{slug}.md").exists():
            continue
        slugs.append(slug)
    return slugs


def reserve_health(remaining: int) -> str:
    if remaining <= RESERVE_CRITICAL_THRESHOLD:
        return "critical"
    if remaining <= RESERVE_WARNING_THRESHOLD:
        return "warning"
    return "healthy"


def choose_reserve(reserve_dir: Path, state: dict[str, Any], day: str) -> tuple[Path, dict[str, Any], str, str] | None:
    used = state.get("fallbackReserves", {})
    for path in sorted(reserve_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        slug = str(data.get("slug", "")).strip()
        if not slug or slug in used:
            continue
        if (ARTICLE_DIR / f"{slug}.md").exists() or (ENGLISH_DIR / f"{slug}.md").exists():
            continue
        jp, en = validate_reserve(data, day)
        return path, data, jp, en
    return None


def materialize_reserve(data: dict[str, Any], jp: str, en: str) -> None:
    slug = data["slug"]
    ARTICLE_DIR.mkdir(parents=True, exist_ok=True)
    ENGLISH_DIR.mkdir(parents=True, exist_ok=True)
    social = SOCIAL_DIR / slug
    social.mkdir(parents=True, exist_ok=True)
    (ARTICLE_DIR / f"{slug}.md").write_text(jp, encoding="utf-8")
    (ENGLISH_DIR / f"{slug}.md").write_text(en, encoding="utf-8")
    (social / "x.md").write_text(data["social_x"].strip() + "\n", encoding="utf-8")
    (social / "linkedin.md").write_text(data["social_linkedin"].strip() + "\n", encoding="utf-8")
    (social / "facebook.md").write_text(data["social_facebook"].strip() + "\n", encoding="utf-8")


def run_normal_path(args: argparse.Namespace) -> tuple[int, dict[str, str]]:
    generator_args = list(args.generator_args)
    if generator_args and generator_args[0] == "--":
        generator_args = generator_args[1:]

    command = [
        sys.executable,
        "scripts/run_drive_editorial_resilient.py",
        "--max-attempts", str(args.max_attempts),
        "--backoff-seconds", str(args.backoff_seconds),
        "--report-path", str(args.report_path),
        "--",
        *generator_args,
    ]
    env = os.environ.copy()
    with tempfile.NamedTemporaryFile(prefix="daily-guarantee-output-", delete=False) as tmp:
        output_path = Path(tmp.name)
    env["GITHUB_OUTPUT"] = str(output_path)
    try:
        completed = subprocess.run(command, env=env, check=False)
        text = output_path.read_text(encoding="utf-8") if output_path.exists() else ""
    finally:
        output_path.unlink(missing_ok=True)
    outputs = parse_outputs(text)
    if completed.returncode != 0 and not outputs.get("reason"):
        outputs["reason"] = "generator_error"
    return completed.returncode, outputs


def main() -> int:
    args = parse_args()
    day = datetime.now(JST).date().isoformat()
    state = load_state(args.state_path)
    reserve_remaining = len(unused_reserve_slugs(args.reserve_dir, state))
    health = reserve_health(reserve_remaining)

    published = published_lhub_slugs_for_day(ARTICLE_DIR, day)
    if published:
        emit({
            "selected": False,
            "reason": "already_published_today",
            "mode": "already_published",
            "published_slug": published[0],
            "reserve_remaining": reserve_remaining,
            "reserve_health": health,
        })
        print(f"Daily Guarantee: LHub article already published today: {published[0]}")
        return 0

    returncode, outputs = run_normal_path(args)
    if outputs.get("selected", "").lower() == "true":
        outputs["mode"] = "generated"
        outputs["reserve_remaining"] = reserve_remaining
        outputs["reserve_health"] = health
        emit(outputs)
        return 0

    reason = outputs.get("reason") or ("generator_error" if returncode else "completed_without_selection")
    if reason not in FALLBACK_REASONS:
        emit({**outputs, "selected": False, "reason": reason, "mode": "normal_failed_no_fallback", "reserve_remaining": reserve_remaining, "reserve_health": health})
        return returncode

    chosen = choose_reserve(args.reserve_dir, state, day)
    if not chosen:
        emit({"selected": False, "reason": "fallback_reserve_exhausted", "mode": "fallback_unavailable", "reserve_remaining": reserve_remaining, "reserve_health": health})
        print("Daily Guarantee: no unused validated LHub reserve remains", file=sys.stderr)
        return 1

    path, data, jp, en = chosen
    materialize_reserve(data, jp, en)
    state.setdefault("fallbackReserves", {})[data["slug"]] = {
        "usedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "trigger": reason,
        "reserveFile": path.name,
    }
    save_state(args.state_path, state)
    remaining_after = len(unused_reserve_slugs(args.reserve_dir, state))
    emit({
        "selected": True,
        "reason": "fallback_reserve",
        "mode": "fallback_reserve",
        "fallback_trigger": reason,
        "slug": data["slug"],
        "score": "reserve",
        "reserve_remaining": remaining_after,
        "reserve_health": reserve_health(remaining_after),
    })
    print(f"Daily Guarantee: materialized reserve {data['slug']} after {reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
