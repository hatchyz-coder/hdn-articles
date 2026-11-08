#!/usr/bin/env python3
"""Prepare seven recovery articles without misrepresenting their publication dates.

This is a manual preparation command, never called by the regular Daily Drive.
It writes files for an independently approved publication PR. It does not push,
merge, deploy or contact external services.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import lhub_daily_guarantee as guarantee

ROOT = Path(__file__).resolve().parents[1]
JST = timezone(timedelta(hours=9))

# The historic dates are *missed slots*, not publication dates.
MANIFEST = {
    "2026-10-31": "33-consent-explanation-timing.json",
    "2026-11-01": "34-staff-escalation-boundary.json",
    "2026-11-02": "35-channel-routing-governance.json",
    "2026-11-03": "36-payment-check-before-service.json",
    "2026-11-04": "37-cancellation-policy-clarity.json",
    "2026-11-05": "38-remote-consultation-preflight.json",
    "2026-11-06": "39-followup-next-action.json",
}


def prepare(root: Path, release_date: date, *, preview: bool = True, refresh_staged: bool = False) -> list[dict[str, str]]:
    if release_date < date(2026, 11, 8):
        raise ValueError("Backfill release must be no earlier than November 8, 2026")
    results = []
    for missed_day, filename in MANIFEST.items():
        source = root / "fallback" / "lhub" / filename
        data = json.loads(source.read_text(encoding="utf-8"))
        slug = data["slug"]
        target_ja = root / "src/content/articles" / f"{slug}.md"
        target_en = root / "src/content/articles-en" / f"{slug}.md"
        if target_ja.exists() or target_en.exists():
            if not refresh_staged or not (target_ja.exists() and target_en.exists()):
                raise FileExistsError(f"Already published or staged: {slug}")
            # Only revise articles explicitly staged for the same missing day.
            for existing in (target_ja, target_en):
                current = existing.read_text(encoding="utf-8")
                if f"backfillFor: {missed_day}" not in current:
                    raise FileExistsError(f"Refusing to overwrite a non-backfill article: {slug}")

        ja, en = guarantee.validate_reserve(data, release_date.isoformat())
        if re.search(r"[\u3040-\u30ff\u3400-\u9fff]", en):
            raise ValueError(f"Mixed-language English backfill: {slug}")

        # Keep the actual publication date in publishedAt, while retaining the
        # historical due date only as recovery metadata.
        note_ja = (f"**掲載補完のお知らせ：** この記事は{missed_day}の未掲載枠を補うため、"
                   f"{release_date.isoformat()}に初めて公開するものです。過去に公開済みだったことを示すものではありません。")
        note_en = (f"**Publication recovery:** This article fills the missed {missed_day} slot. "
                   f"It is first published on {release_date.isoformat()}, not backdated.")
        def annotate(text: str, note: str) -> str:
            return text.replace("---\n\n", f"backfillFor: {missed_day}\n---\n\n{note}\n\n", 1)
        ja = annotate(ja, note_ja)
        en = annotate(en, note_en)
        results.append({"original_due_date": missed_day, "released_on": release_date.isoformat(), "slug": slug})
        if not preview:
            target_ja.parent.mkdir(parents=True, exist_ok=True)
            target_en.parent.mkdir(parents=True, exist_ok=True)
            target_ja.write_text(ja, encoding="utf-8")
            target_en.write_text(en, encoding="utf-8")
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--release-date", type=date.fromisoformat, default=datetime.now(JST).date())
    parser.add_argument("--write", action="store_true", help="write local Markdown; does not push or deploy")
    parser.add_argument("--refresh-staged", action="store_true", help="only replace matching backfillFor articles, useful if approval moves the actual release day")
    args = parser.parse_args()
    if args.refresh_staged and not args.write:
        parser.error("--refresh-staged requires --write")
    result = prepare(args.root, args.release_date, preview=not args.write, refresh_staged=args.refresh_staged)
    print(json.dumps({"preview": not args.write, "backfill": result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
