#!/usr/bin/env python3
"""Validate machine-readable evidence for World Frictions end-to-end completion."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from publication_completion_gate import Evidence, completion_label, facebook_copy_valid, resolve_state, State


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug", required=True)
    parser.add_argument("--evidence", required=True, type=Path)
    return parser.parse_args()


def evaluate(slug: str, payload: dict) -> dict:
    if payload.get("slug") != slug:
        raise ValueError("evidence slug does not match requested slug")
    evidence = Evidence(
        jp_exists=bool(payload.get("jp_exists")),
        en_exists=bool(payload.get("en_exists")),
        canonical_live=bool(payload.get("canonical_live")),
        social_provider_id=str(payload.get("social_provider_id") or ""),
        social_status=str(payload.get("social_status") or ""),
        social_live_evidence=bool(payload.get("social_live_evidence")),
        social_evidence_source=str(payload.get("social_evidence_source") or ""),
        duplicate_free=bool(payload.get("duplicate_free")),
        facebook_chars=int(payload.get("facebook_chars") or 0),
    )
    copy_ok = facebook_copy_valid(evidence.facebook_chars, bool(payload.get("facebook_editorial_exception")))
    state = resolve_state(evidence)
    complete = state is State.SOCIAL_LIVE and copy_ok
    return {
        "slug": slug,
        "state": state.name,
        "result": "COMPLETED" if complete else "INCOMPLETE",
        "completion_label": completion_label(evidence) if copy_ok else "INCOMPLETE",
        "facebook_copy_valid": copy_ok,
    }


def main() -> int:
    args = parse_args()
    payload = json.loads(args.evidence.read_text(encoding="utf-8"))
    result = evaluate(args.slug, payload)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["result"] == "COMPLETED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
