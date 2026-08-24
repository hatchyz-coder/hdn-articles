#!/usr/bin/env python3
"""Build the canonical official-source editorial queue from persistent collector candidates."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTICLE_DIR = ROOT / "src" / "content" / "articles"
DEFAULT_OFFICIAL = ROOT / "data" / "official-sources" / "candidates.json"
DEFAULT_PENDING = ROOT / "data" / "official-sources" / "editorial-pending.json"
DEFAULT_OUTPUT = ROOT / "data" / "candidates" / "latest.json"
MAX_PENDING = 5000
MAX_PER_SOURCE_IN_TOP_WINDOW = 2


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def published_source_urls() -> set[str]:
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


def normalized_candidate(item: dict[str, Any]) -> dict[str, Any] | None:
    url = str(item.get("url", "")).strip()
    title = str(item.get("title", "")).strip()
    if not url.startswith(("https://", "http://")) or not title:
        return None
    source_name = str(item.get("source_name") or item.get("source") or "Official source").strip()
    source_id = str(item.get("source_id") or source_name).strip()
    score = int(item.get("score", item.get("ai_score", 0)) or 0)
    priority = int(item.get("priority", item.get("source_priority", 0)) or 0)
    matched = [str(v) for v in item.get("matched_keywords", []) if str(v).strip()]
    identifier = str(item.get("fingerprint") or hashlib.sha256(url.encode("utf-8")).hexdigest())
    failures = int(item.get("generation_failures", 0) or 0)
    return {
        **item,
        "id": identifier[:16], "source_id": source_id, "source_name": source_name, "source": source_name,
        "url": url, "title": title, "score": score, "ai_score": score, "source_priority": priority,
        "keyword_score": max(int(item.get("keyword_score", 0) or 0), min(30, len(matched) * 10)),
        "reason": str(item.get("reason") or f"Official-source update from {source_name}; editorial value is evaluated separately from urgency."),
        "suggested_category": str(item.get("suggested_category") or "コンプライアンス・行政"),
        "suggested_cta": str(item.get("suggested_cta") or "consultation"),
        "suggested_slug": str(item.get("suggested_slug") or ""),
        "discovered_at": str(item.get("discovered_at") or datetime.now(timezone.utc).isoformat()),
        "generation_failures": failures,
    }


def merge_pending(existing: list[dict[str, Any]], fresh: list[dict[str, Any]], published: set[str]) -> list[dict[str, Any]]:
    by_url: dict[str, dict[str, Any]] = {}
    for raw in [*existing, *fresh]:
        item = normalized_candidate(raw)
        if not item or item["url"] in published:
            continue
        current = by_url.get(item["url"])
        if current is None:
            by_url[item["url"]] = item
            continue
        # Fresh collector metadata may improve, but operational failure history must survive
        # rediscovery so the same bad source cannot monopolize every day.
        merged = {**current, **item}
        merged["generation_failures"] = max(int(current.get("generation_failures", 0) or 0), int(item.get("generation_failures", 0) or 0))
        if current.get("last_generation_failure_at"):
            merged["last_generation_failure_at"] = current["last_generation_failure_at"]
        by_url[item["url"]] = merged

    def rank(item: dict[str, Any]) -> tuple[Any, ...]:
        failures = int(item.get("generation_failures", 0) or 0)
        effective_score = int(item.get("score", 0)) - min(50, failures * 10)
        return (effective_score, int(item.get("source_priority", 0)), str(item.get("published_at", "")), str(item.get("discovered_at", "")))

    return sorted(by_url.values(), key=rank, reverse=True)[:MAX_PENDING]


def fair_top_window(pending: list[dict[str, Any]], limit: int = 100) -> list[dict[str, Any]]:
    chosen: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []
    per_source: dict[str, int] = {}
    for item in pending:
        source = str(item.get("source_id") or item.get("source_name") or "unknown")
        if per_source.get(source, 0) < MAX_PER_SOURCE_IN_TOP_WINDOW:
            chosen.append(item)
            per_source[source] = per_source.get(source, 0) + 1
        else:
            deferred.append(item)
        if len(chosen) >= limit:
            return chosen[:limit]
    for item in deferred:
        if len(chosen) >= limit:
            break
        chosen.append(item)
    return chosen[:limit]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--official-path", type=Path, default=DEFAULT_OFFICIAL)
    parser.add_argument("--pending-path", type=Path, default=DEFAULT_PENDING)
    parser.add_argument("--output-path", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    official = load_json(args.official_path, {"candidates": []}).get("candidates", [])
    existing = load_json(args.pending_path, {"candidates": []}).get("candidates", [])
    published = published_source_urls()
    pending = merge_pending(existing, official, published)
    selection_queue = fair_top_window(pending)
    now = datetime.now(timezone.utc).isoformat()
    write_json(args.pending_path, {"generated_at": now, "candidates": pending})
    write_json(args.output_path, {"generated_at": now, "source_mode": "official_20_source_pending", "candidates": selection_queue})
    print(f"Prepared official editorial pending queue: pending={len(pending)} selectable={len(selection_queue)} published_removed={len(published)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
