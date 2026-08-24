#!/usr/bin/env python3
"""Update operational metadata for one pending official-source candidate."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pending-path", type=Path, required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--outcome", choices=["generation_failed", "published"], required=True)
    args = parser.parse_args()

    if not args.pending_path.exists():
        return 0
    payload = json.loads(args.pending_path.read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc).isoformat()
    changed = False
    remaining = []
    for item in payload.get("candidates", []):
        if str(item.get("url", "")) != args.url:
            remaining.append(item)
            continue
        changed = True
        if args.outcome == "published":
            continue
        updated = dict(item)
        updated["generation_failures"] = int(updated.get("generation_failures", 0) or 0) + 1
        updated["last_generation_failure_at"] = now
        remaining.append(updated)
    if changed:
        payload["generated_at"] = now
        payload["candidates"] = remaining
        args.pending_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
