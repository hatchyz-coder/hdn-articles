#!/usr/bin/env python3
"""Audit the existing WordPress article site before switching to Astro."""
from __future__ import annotations

import csv
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "data" / "migration"
REPORT_DIR = ROOT / "reports" / "migration"
OLD_SITE = "https://article.hdnjapan.com"
SITEMAP_CANDIDATES = [
    f"{OLD_SITE}/wp-sitemap.xml",
    f"{OLD_SITE}/sitemap_index.xml",
    f"{OLD_SITE}/sitemap.xml",
]
HEADERS = {"User-Agent": "HDN-Migration-Audit/1.0 (+https://hdnjapan.com/)"}


def fetch_xml(url: str) -> ET.Element:
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return ET.fromstring(response.content)


def locs(root: ET.Element) -> list[str]:
    return [node.text.strip() for node in root.findall(".//{*}loc") if node.text]


def discover_sitemap_urls() -> tuple[str, list[str]]:
    last_error = None
    for candidate in SITEMAP_CANDIDATES:
        try:
            root = fetch_xml(candidate)
            urls = locs(root)
            if root.tag.endswith("sitemapindex"):
                page_urls: list[str] = []
                for child in urls:
                    try:
                        page_urls.extend(locs(fetch_xml(child)))
                    except Exception as exc:
                        print(f"WARN sitemap child {child}: {exc}")
                return candidate, sorted(set(page_urls))
            return candidate, sorted(set(urls))
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"No sitemap could be loaded: {last_error}")


def existing_new_slugs() -> set[str]:
    article_dir = ROOT / "src" / "content" / "articles"
    return {path.stem for path in article_dir.glob("*.md")}


def classify(url: str, new_slugs: set[str]) -> dict[str, str]:
    path = urlparse(url).path.rstrip("/")
    slug = path.split("/")[-1] if path else ""
    text = path.lower()
    medical_terms = [
        "medical", "clinic", "lhub", "line", "yakki", "keihyo", "health",
        "online", "regenerative", "doctor", "hospital", "自由診療", "医療",
    ]
    low_priority_terms = ["recruit", "travel", "food", "restaurant", "event", "entertainment"]

    if slug in new_slugs:
        status = "already_migrated"
        action = "新サイト側の記事と照合し、canonicalと旧URL対応を確認"
    elif any(term in text for term in low_priority_terms):
        status = "review_or_remove"
        action = "HDN事業との関連性を確認し、削除または統合を判断"
    elif any(term in text for term in medical_terms):
        status = "priority_migrate"
        action = "医療・LHub・自由診療領域として優先移行"
    else:
        status = "manual_review"
        action = "タイトルと本文を確認して移行可否を判断"

    return {"url": url, "slug": slug, "status": status, "recommended_action": action}


def main() -> None:
    sitemap_url, urls = discover_sitemap_urls()
    new_slugs = existing_new_slugs()
    rows = [classify(url, new_slugs) for url in urls if url.startswith(OLD_SITE)]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    csv_path = OUTPUT_DIR / "old-wordpress-urls.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["url", "slug", "status", "recommended_action"])
        writer.writeheader()
        writer.writerows(rows)

    summary: dict[str, int] = {}
    for row in rows:
        summary[row["status"]] = summary.get(row["status"], 0) + 1

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_sitemap": sitemap_url,
        "total_urls": len(rows),
        "summary": summary,
        "rows": rows,
    }
    (OUTPUT_DIR / "old-wordpress-urls.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lines = [
        "# article.hdnjapan.com 移行監査レポート",
        "",
        f"- 取得元サイトマップ: {sitemap_url}",
        f"- 旧URL総数: **{len(rows)}件**",
        "",
        "## 判定集計",
        "",
    ]
    labels = {
        "priority_migrate": "優先移行",
        "already_migrated": "移行済み候補",
        "manual_review": "要手動確認",
        "review_or_remove": "統合・削除候補",
    }
    for key, label in labels.items():
        lines.append(f"- {label}: {summary.get(key, 0)}件")

    lines += [
        "",
        "## 切替前の必須条件",
        "",
        "- 主要記事の移行先URLを確定する",
        "- 旧URLと新URLの対応表を作る",
        "- 旧URLを失う場合は301リダイレクト方法を別途確保する",
        "- canonical、sitemap、RSS、OGP、構造化データを確認する",
        "- GitHub PagesのCustom domainへ article.hdnjapan.com を設定する",
        "- DNSのCNAMEを hatchyz-coder.github.io に切り替える",
        "- HTTPS有効化後にSearch Consoleと主要URLを確認する",
        "",
        "> この処理は監査のみです。DNS、WordPress、本番ドメインは変更しません。",
        "",
    ]
    (REPORT_DIR / "latest.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Audited {len(rows)} WordPress URLs")


if __name__ == "__main__":
    main()
