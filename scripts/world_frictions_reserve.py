#!/usr/bin/env python3
"""Materialize a pre-validated World Frictions reserve when the live provider is unavailable."""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESERVE_DIR = ROOT / "fallback" / "world-frictions"
ARTICLE_DIR = ROOT / "src" / "content" / "articles"
EN_ARTICLE_DIR = ROOT / "src" / "content" / "articles-en"
SOCIAL_DIR = ROOT / "social"
JST = timezone(timedelta(hours=9))


def _write_output(**values: object) -> None:
    output = os.getenv("GITHUB_OUTPUT")
    if not output:
        return
    with open(output, "a", encoding="utf-8") as handle:
        for key, value in values.items():
            handle.write(f"{key}={value}\n")


def _render(value: str, *, date: str, url: str) -> str:
    return value.replace("{{DATE}}", date).replace("{{URL}}", url)


def choose_reserve() -> tuple[Path, dict] | None:
    for path in sorted(RESERVE_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        slug = str(data.get("slug") or "").strip()
        if not slug:
            continue
        if (ARTICLE_DIR / f"{slug}.md").exists() or (EN_ARTICLE_DIR / f"{slug}.md").exists():
            continue
        return path, data
    return None


def materialize_next_reserve(reason: str) -> dict[str, str] | None:
    chosen = choose_reserve()
    if chosen is None:
        return None
    path, data = chosen
    slug = str(data["slug"])
    title = str(data["title"])
    today = datetime.now(JST).date().isoformat()
    url = f"https://article.hdnjapan.com/articles/{slug}/"

    ARTICLE_DIR.mkdir(parents=True, exist_ok=True)
    EN_ARTICLE_DIR.mkdir(parents=True, exist_ok=True)
    target_social = SOCIAL_DIR / slug
    target_social.mkdir(parents=True, exist_ok=True)

    (ARTICLE_DIR / f"{slug}.md").write_text(
        _render(str(data["jp"]), date=today, url=url).rstrip() + "\n",
        encoding="utf-8",
    )
    (EN_ARTICLE_DIR / f"{slug}.md").write_text(
        _render(str(data["en"]), date=today, url=url).rstrip() + "\n",
        encoding="utf-8",
    )
    social = data.get("social") or {}
    required = ("note.md", "linkedin-newsletter.md", "linkedin.md", "facebook.md", "x.md", "reposts.md")
    for name in required:
        if name not in social:
            raise ValueError(f"World Frictions reserve missing {name}: {path}")
        (target_social / name).write_text(
            _render(str(social[name]), date=today, url=url).rstrip() + "\n",
            encoding="utf-8",
        )

    result = {
        "slug": slug,
        "title": title,
        "canonical_url": url,
        "reason": f"validated_reserve_after_provider_failure:{reason}",
    }
    _write_output(publish="true", **result)
    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(
                "## World Frictions validated reserve\n\n"
                f"- Slug: \`{slug}\`\n"
                f"- Trigger: {reason}\n"
                f"- Reserve: {path.relative_to(ROOT)}\n"
            )
    print(json.dumps({"publish": True, **result}, ensure_ascii=False))
    return result


if __name__ == "__main__":
    result = materialize_next_reserve("manual_reserve_materialization")
    raise SystemExit(0 if result else 2)
