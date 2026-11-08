#!/usr/bin/env python3
"""Read-only JST-day LHub publication and reserve inventory audit."""
from __future__ import annotations

import argparse
import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))

def field(text: str, key: str) -> str:
    if not text.startswith("---"):
        return ""
    header = text.split("---", 2)[1]
    match = re.search(rf"(?m)^{re.escape(key)}:\s*['\"]?([^\n'\"]+)", header)
    return match.group(1).strip() if match else ""

def published(article_dir: Path) -> dict[str, list[str]]:
    days = {}
    for path in article_dir.glob("*.md"):
        body = path.read_text(encoding="utf-8")
        if field(body, "draft").lower() == "true" or field(body, "backfillFor"):
            continue
        if field(body, "section") != "lhub-usecase" and not re.search(
            r'(?m)^\s+-\s*["\']?lhub["\']?\s*$', body.split("---", 2)[1] if body.startswith("---") else ""
        ):
            continue
        day = field(body, "publishedAt")
        try:
            date.fromisoformat(day)
        except ValueError:
            continue
        days.setdefault(day, []).append(path.stem)
    return {d: sorted(v) for d, v in days.items()}

def backfilled(article_dir: Path) -> dict[str, list[str]]:
    """Index supplementary releases by originally missed day, without backdating."""
    days: dict[str, list[str]] = {}
    for path in article_dir.glob("*.md"):
        content = path.read_text(encoding="utf-8")
        missed = field(content, "backfillFor")
        if not missed or field(content, "draft").lower() == "true":
            continue
        published_day = field(content, "publishedAt")
        try:
            if date.fromisoformat(published_day) < date.fromisoformat(missed):
                continue
        except ValueError:
            continue
        days.setdefault(missed, []).append(path.stem)
    return {day: sorted(slugs) for day, slugs in days.items()}


def reserve_inventory(reserve_dir: Path, state: dict, jp: Path, en: Path) -> dict:
    used = state.get("fallbackReserves", {})
    total, available, malformed = 0, [], []
    for path in sorted(reserve_dir.glob("*.json")):
        total += 1
        try:
            slug = str(json.loads(path.read_text(encoding="utf-8"))["slug"])
        except (KeyError, ValueError, OSError, TypeError):
            malformed.append(path.name)
            continue
        if slug not in used and not (jp / (slug + ".md")).exists() and not (en / (slug + ".md")).exists():
            available.append(slug)
    return {"total": total, "used_in_state": len(used), "remaining": len(available),
            "available_slugs": available, "malformed": malformed}

def audit(root: Path, start: date, end: date) -> dict:
    jp = root / "src/content/articles"
    state_file = root / "data/editorial-drive/processed-docs.json"
    state = json.loads(state_file.read_text(encoding="utf-8")) if state_file.exists() else {}
    days = published(jp)
    recovery = backfilled(jp)
    span = [start + timedelta(days=i) for i in range(max(0, (end - start).days + 1))]
    missed = [d.isoformat() for d in span if not days.get(d.isoformat())]
    return {
        "range": [start.isoformat(), end.isoformat()],
        "published": {d: v for d, v in days.items() if start.isoformat() <= d <= end.isoformat()},
        "missing_days": missed,
        "backfilled_days": {d: recovery[d] for d in missed if recovery.get(d)},
        "uncompensated_days": [d for d in missed if not recovery.get(d)],
        "duplicate_days": {d: v for d, v in days.items() if len(v) > 1 and start.isoformat() <= d <= end.isoformat()},
        "reserve": reserve_inventory(root / "fallback/lhub", state, jp, root / "src/content/articles-en"),
        "state_updated_at": state.get("updatedAt"),
        "processed_documents": len(state.get("documents", {})),
    }

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--since", type=date.fromisoformat, default=date(2026, 10, 31))
    parser.add_argument("--until", type=date.fromisoformat, default=datetime.now(JST).date())
    parser.add_argument("--output", type=Path)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    data = audit(args.root, args.since, args.until)
    output = json.dumps(data, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + "\n", encoding="utf-8")
    print(output)
    return int(args.strict and bool(data["missing_days"] or data["duplicate_days"] or data["reserve"]["remaining"] == 0))

if __name__ == "__main__":
    raise SystemExit(main())
