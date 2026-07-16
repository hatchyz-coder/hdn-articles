from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "sources.json"
DATA_DIR = ROOT / "data"
SEEN_PATH = DATA_DIR / "seen-urls.json"
LATEST_PATH = DATA_DIR / "candidates" / "latest.json"

HEADERS = {
    "User-Agent": "HDN-Articles-Discovery/1.0 (+https://hdnjapan.com/)"
}


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def url_allowed(url: str, domains: list[str]) -> bool:
    host = urlparse(url).netloc.lower()
    return any(host == d or host.endswith(f".{d}") for d in domains)


def keyword_score(title: str, keywords: list[str], exclude: list[str]) -> int:
    if any(word in title for word in exclude):
        return -100
    return sum(2 for word in keywords if word.lower() in title.lower())


def fetch_links(source: dict[str, Any]) -> list[dict[str, Any]]:
    response = requests.get(source["url"], headers=HEADERS, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    soup = BeautifulSoup(response.text, "html.parser")

    results: list[dict[str, Any]] = []
    seen_local: set[str] = set()
    for anchor in soup.select("a[href]"):
        title = normalize_text(anchor.get_text(" ", strip=True))
        if len(title) < 8:
            continue
        url = urljoin(source["url"], anchor.get("href", ""))
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            continue
        url = parsed._replace(fragment="").geturl()
        if not url_allowed(url, source.get("domains", [])):
            continue
        if url in seen_local:
            continue
        seen_local.add(url)
        results.append({
            "title": title,
            "url": url,
            "source": source["name"],
            "source_priority": int(source.get("priority", 1)),
        })
    return results


def ai_rank(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or not candidates:
        return candidates

    compact = [
        {"id": i, "title": c["title"], "source": c["source"], "url": c["url"]}
        for i, c in enumerate(candidates)
    ]
    prompt = (
        "HDN JapanのSEO記事候補を選別してください。対象読者はクリニック経営者、医療事業者です。"
        "自由診療、医療広告、薬機法、景表法、再生医療、医療DX、患者導線、LINE、予約、決済、CRMとの関連性、"
        "検索意図、問い合わせへのつながりやすさ、情報の重要性を評価してください。"
        "JSON配列のみを返し、各要素を "
        "{id, ai_score, reason, suggested_category, suggested_cta, suggested_slug} としてください。"
        "ai_scoreは0〜100、suggested_ctaはconsultation/lhub/self-payのいずれかです。"
        "suggested_slugは検索意図が分かる英小文字・数字・ハイフンのみ、3〜8語程度としてください。\n\n"
        + json.dumps(compact, ensure_ascii=False)
    )
    payload = {
        "model": os.getenv("OPENAI_MODEL", "gpt-5-mini"),
        "input": prompt,
    }
    response = requests.post(
        "https://api.openai.com/v1/responses",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=120,
    )
    response.raise_for_status()
    data = response.json()
    text = data.get("output_text", "")
    if not text:
        chunks: list[str] = []
        for item in data.get("output", []):
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    chunks.append(content.get("text", ""))
        text = "".join(chunks)
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.I | re.S)
    ranked = json.loads(text)
    by_id = {int(item["id"]): item for item in ranked}
    for idx, candidate in enumerate(candidates):
        ai = by_id.get(idx, {})
        candidate["ai_score"] = int(ai.get("ai_score", 0))
        candidate["reason"] = ai.get("reason", "")
        candidate["suggested_category"] = ai.get("suggested_category", "医療経営")
        candidate["suggested_cta"] = ai.get("suggested_cta", "consultation")
        candidate["suggested_slug"] = ai.get("suggested_slug", "")
    return candidates


def main() -> None:
    config = load_json(CONFIG_PATH, {})
    seen = set(load_json(SEEN_PATH, []))
    keywords = config.get("keywords", [])
    exclude = config.get("exclude_keywords", [])

    candidates: list[dict[str, Any]] = []
    for source in config.get("sources", []):
        try:
            links = fetch_links(source)
        except Exception as exc:
            print(f"WARN {source['name']}: {exc}")
            continue
        for item in links:
            if item["url"] in seen:
                continue
            score = keyword_score(item["title"], keywords, exclude)
            if score <= 0:
                continue
            item["keyword_score"] = score
            item["discovered_at"] = datetime.now(timezone.utc).isoformat()
            item["id"] = hashlib.sha256(item["url"].encode()).hexdigest()[:16]
            candidates.append(item)

    candidates.sort(key=lambda x: (x["keyword_score"], x["source_priority"]), reverse=True)
    candidates = candidates[: int(config.get("max_candidates_per_run", 20))]
    candidates = ai_rank(candidates)
    candidates.sort(
        key=lambda x: (x.get("ai_score", 0), x["keyword_score"], x["source_priority"]),
        reverse=True,
    )

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LATEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    LATEST_PATH.write_text(
        json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(), "candidates": candidates}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    seen.update(item["url"] for item in candidates)
    SEEN_PATH.write_text(json.dumps(sorted(seen), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Discovered {len(candidates)} candidates")


if __name__ == "__main__":
    main()
