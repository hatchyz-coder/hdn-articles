#!/usr/bin/env python3
"""Promote merged Drive editorial records to published only after JP/EN URLs return 2xx."""
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_BASE_URL = "https://article.hdnjapan.com"


def article_urls(slug: str, base_url: str = DEFAULT_BASE_URL) -> tuple[str, str]:
    base = base_url.rstrip("/")
    return f"{base}/articles/{slug}/", f"{base}/en/articles/{slug}/"


def url_is_live(url: str, timeout: float = 15.0) -> bool:
    request = urllib.request.Request(url, headers={"User-Agent": "HDN-Publication-Verifier/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return 200 <= int(response.status) < 300
    except (urllib.error.URLError, TimeoutError, ValueError):
        return False


def pair_is_live(slug: str, base_url: str, retries: int, sleep_seconds: float) -> bool:
    jp, en = article_urls(slug, base_url)
    for attempt in range(max(1, retries)):
        if url_is_live(jp) and url_is_live(en):
            return True
        if attempt + 1 < max(1, retries):
            time.sleep(max(0.0, sleep_seconds))
    return False


def reconcile_state(
    state: dict[str, Any],
    base_url: str,
    required_slug: str,
    retries: int,
    sleep_seconds: float,
) -> tuple[int, bool]:
    promoted = 0
    required_live = False
    now = datetime.now(timezone.utc).isoformat()
    for record in state.get("documents", {}).values():
        if record.get("status") != "generated":
            continue
        slug = str(record.get("slug", "")).strip()
        if not slug:
            continue
        live = pair_is_live(slug, base_url, retries if slug == required_slug else 1, sleep_seconds)
        if live:
            record["status"] = "published"
            record["publishedAt"] = now
            promoted += 1
            if slug == required_slug:
                required_live = True
    if required_slug and not required_live:
        # The current publication is not complete until both language URLs are live.
        return promoted, False
    state["updatedAt"] = now
    return promoted, True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-path", type=Path, required=True)
    parser.add_argument("--required-slug", default="")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--retries", type=int, default=12)
    parser.add_argument("--sleep-seconds", type=float, default=10.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    state = json.loads(args.state_path.read_text(encoding="utf-8"))
    promoted, required_live = reconcile_state(
        state,
        args.base_url,
        args.required_slug,
        args.retries,
        args.sleep_seconds,
    )
    args.state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Promoted {promoted} merged article record(s) to published.")
    if not required_live:
        print(f"Required JP/EN production pair is not live: {args.required_slug}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
