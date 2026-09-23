#!/usr/bin/env python3
"""Build an auditable Facebook candidate ledger from published HDN articles."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
ARTICLE_DIR = ROOT / "src/content/articles"
SOCIAL_DIR = ROOT / "social"
CANONICAL_ROOT = "https://article.hdnjapan.com/articles"
DEFAULT_PLAN = ROOT / "data/facebook-editorial-plan.json"


def field(text: str, name: str) -> str:
    match = re.search(rf"(?m)^{re.escape(name)}:\s*[\"']?(.*?)[\"']?\s*$", text)
    return match.group(1).strip() if match else ""


def clean_url(url: str) -> str:
    parts = urlsplit(url.strip())
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/") + "/", "", ""))


def duplicate_key(url: str, copy: str) -> str:
    normalized = re.sub(r"\s+", " ", copy).strip()
    return hashlib.sha256(f"facebook\n{clean_url(url)}\n{normalized}".encode()).hexdigest()


@dataclass
class Record:
    article_id: str
    title: str
    category: str
    canonical_status: str
    public_url: str
    facebook_copy_path: str
    facebook_copy: str
    source_count: int
    reader_value_score: int
    score_breakdown: dict[str, int]
    decision: str
    decision_reason: str
    desired_schedule_at: str | None
    duplicate_key: str
    metricool_post_id: str | None
    metricool_uuid: str | None
    post_status: str
    facebook_post_url: str | None


def evaluate(path: Path, evidence: dict, desired_at: str | None) -> Record:
    article = path.read_text(encoding="utf-8")
    slug = path.stem
    title, category = field(article, "title"), field(article, "category")
    is_published = field(article, "draft").lower() == "false"
    url = f"{CANONICAL_ROOT}/{slug}/"
    fb_path = SOCIAL_DIR / slug / "facebook.md"
    copy = fb_path.read_text(encoding="utf-8").strip() if fb_path.exists() else ""
    body = article.split("---", 2)[-1]
    sources = {u.rstrip("/).,") for u in re.findall(r"https?://[^\s>]+", body)}
    if field(article, "sourceUrl"):
        sources.add(field(article, "sourceUrl"))
    section_count = len(re.findall(r"(?m)^#{2,3}\s+", body))
    practical_steps = len(re.findall(r"(?m)^###\s+(?:\d+[.．]|チェック|確認)", body))
    concrete_mentions = len(re.findall(r"\d|事例|調査|報告|命じ|公表", body))
    utility_mentions = len(re.findall(r"設計|確認|判断|必要|仕組み|選択|運用|導線|対応", body))
    perspective_signal = re.search(
        r"HDNの視点|私は|僕は|私自身|違和感|と思います|重要なのは|DXは|成功する",
        body,
    )
    breakdown = {
        "facebook_fit": 20 if 1000 <= len(copy) <= 1800 and copy.startswith("【") else 0,
        "evidence": min(20, len(sources) * 5),
        "concrete_examples": 15 if concrete_mentions >= 8 or practical_steps >= 4 else 5,
        "reader_utility": 15 if utility_mentions >= 8 else 5,
        "hatch_perspective": 15 if perspective_signal else 0,
        "article_depth": 15 if len(body) >= 2400 and section_count >= 4 else 5,
    }
    score = sum(breakdown.values())
    key = duplicate_key(url, copy) if copy else hashlib.sha256(f"facebook\n{clean_url(url)}".encode()).hexdigest()
    prior = evidence.get(key) or evidence.get(clean_url(url)) or {}

    if not is_published:
        decision, reason, status = "not_eligible", "canonical_not_published", "not_published"
    elif prior and prior.get("status") == "scheduled":
        decision = "candidate_selected"
        status = "scheduled"
        reason = "passed_reader_value_gate_and_metricool_reservation_reconciled"
    elif prior:
        decision = "already_distributed"
        status = prior.get("status", "unknown")
        reason = "duplicate_existing_metricool_or_facebook_record"
    elif not copy:
        decision, reason, status = "rejected", "facebook_copy_missing", "canonical_published"
    elif breakdown["facebook_fit"] == 0:
        decision, reason, status = "rejected", "facebook_copy_not_standalone_or_outside_editorial_range", "canonical_published"
    elif len(sources) < 2:
        decision, reason, status = "rejected", "insufficient_verifiable_sources", "canonical_published"
    elif score < 80:
        decision, reason, status = "rejected", f"reader_value_score_below_80:{score}", "canonical_published"
    else:
        decision, reason, status = "candidate_selected", "passed_reader_value_and_facebook_fit_gates", "candidate_selected"

    try:
        facebook_copy_path = str(fb_path.relative_to(ROOT))
    except ValueError:
        facebook_copy_path = str(fb_path)
    return Record(
        slug, title, category, "published" if is_published else "draft", url,
        facebook_copy_path if fb_path.exists() else "", copy, len(sources), score,
        breakdown, decision, reason, desired_at if decision == "candidate_selected" else None,
        key, prior.get("metricool_post_id"), prior.get("metricool_uuid"), status,
        prior.get("facebook_post_url"),
    )


def load_plan(plan_path: Path) -> dict[str, str]:
    if not plan_path.exists():
        return {}
    document = json.loads(plan_path.read_text(encoding="utf-8"))
    items = document.get("posts", [])
    plan = {item["article_id"]: item["scheduled_at"] for item in items}
    if len(plan) != len(items):
        raise ValueError("facebook editorial plan contains duplicate article_id values")
    moments = []
    for article_id, value in plan.items():
        moment = datetime.fromisoformat(value)
        if moment.tzinfo is None:
            raise ValueError(f"scheduled_at must include timezone: {article_id}")
        moments.append((moment, article_id))
    moments.sort()
    for (previous, _), (current, article_id) in zip(moments, moments[1:]):
        if (current - previous).total_seconds() < 60 * 60 * 48:
            raise ValueError(f"Facebook posts must be spaced by at least 48 hours: {article_id}")
    return plan


def build_ledger(evidence_path: Path, desired_at: str | None, plan_path: Path = DEFAULT_PLAN) -> dict:
    evidence_doc = json.loads(evidence_path.read_text(encoding="utf-8")) if evidence_path.exists() else {"records": []}
    evidence = {}
    for item in evidence_doc.get("records", []):
        if item.get("duplicate_key"):
            evidence[item["duplicate_key"]] = item
        if item.get("public_url"):
            evidence[clean_url(item["public_url"])] = item
    plan = load_plan(plan_path)
    records = [evaluate(p, evidence, plan.get(p.stem, desired_at)) for p in sorted(ARTICLE_DIR.glob("*.md"))]
    published = [r for r in records if r.canonical_status == "published"]
    return {
        "schema_version": 1,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "policy": {
            "minimum_reader_value_score": 80,
            "minimum_schedule_gap_hours": 48,
            "filler_forbidden": True,
            "all_categories_scanned": True,
        },
        "summary": {
            "published_articles": len(published),
            "selected": sum(r.decision == "candidate_selected" for r in records),
            "already_distributed": sum(r.decision == "already_distributed" for r in records),
            "rejected": sum(r.decision == "rejected" for r in records),
        },
        "records": [asdict(r) for r in records if r.canonical_status == "published"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, default=ROOT / "data/facebook-publishing-evidence.json")
    parser.add_argument("--output", type=Path, default=ROOT / "data/facebook-post-ledger.json")
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--desired-at", help="ISO 8601 timestamp including timezone")
    args = parser.parse_args()
    if args.desired_at:
        parsed = datetime.fromisoformat(args.desired_at)
        if parsed.tzinfo is None:
            raise SystemExit("--desired-at must include a timezone")
    ledger = build_ledger(args.evidence, args.desired_at, args.plan)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(ledger["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
