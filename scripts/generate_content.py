#!/usr/bin/env python3
"""Generate an HDN article draft and social copy from a source URL."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
ARTICLE_DIR = ROOT / "src" / "content" / "articles"
SOCIAL_DIR = ROOT / "social"
EN_DRAFT_DIR = ROOT / "outputs" / "en"
PROMPT_PATH = ROOT / "prompts" / "article-system.md"

ALLOWED_LINKS = [
    {"label": "HDN Japan", "url": "https://hdnjapan.com/"},
    {"label": "自由診療導入支援", "url": "https://hdnjapan.com/self-pay.html"},
    {"label": "LHub", "url": "https://hdnjapan.com/lhub.html"},
    {"label": "無料相談", "url": "https://forms.gle/148jgfSnDgDZ2HsEA"},
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--category", default="医療経営")
    parser.add_argument("--cta", choices=["consultation", "lhub", "self-pay"], default="consultation")
    return parser.parse_args()


def validate_slug(slug: str) -> str:
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        raise ValueError("slug must contain lowercase letters, numbers, and hyphens only")
    return slug


def fetch_source(url: str) -> tuple[str, str]:
    response = requests.get(
        url,
        timeout=30,
        headers={"User-Agent": "HDN-Content-Engine/1.0 (+https://hdnjapan.com/)"},
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    for node in soup(["script", "style", "noscript", "svg", "form", "nav", "footer"]):
        node.decompose()

    title = soup.title.get_text(" ", strip=True) if soup.title else url
    candidates = soup.select("article, main, [role=main]")
    target = max(candidates, key=lambda n: len(n.get_text(" ", strip=True)), default=soup.body or soup)
    text = "\n".join(
        line.strip() for line in target.get_text("\n", strip=True).splitlines() if line.strip()
    )
    if len(text) < 300:
        raise RuntimeError("Source page text was too short to generate a reliable article")
    return title[:300], text[:30000]


def call_openai(source_url: str, source_title: str, source_text: str, category: str, cta: str) -> dict[str, Any]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured in GitHub Actions secrets")

    model = os.environ.get("OPENAI_MODEL", "gpt-5-mini")
    instructions = PROMPT_PATH.read_text(encoding="utf-8")
    user_input = {
        "source_url": source_url,
        "source_title": source_title,
        "source_text": source_text,
        "requested_category": category,
        "cta_type": cta,
        "allowed_links": ALLOWED_LINKS,
    }

    response = requests.post(
        "https://api.openai.com/v1/responses",
        timeout=180,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "instructions": instructions,
            "input": json.dumps(user_input, ensure_ascii=False),
            "max_output_tokens": 7000,
            "store": False,
        },
    )
    response.raise_for_status()
    payload = response.json()

    output_text = payload.get("output_text")
    if not output_text:
        pieces: list[str] = []
        for item in payload.get("output", []):
            if item.get("type") != "message":
                continue
            for content in item.get("content", []):
                if content.get("type") == "output_text" and content.get("text"):
                    pieces.append(content["text"])
        output_text = "\n".join(pieces)

    if not output_text:
        raise RuntimeError("OpenAI response did not contain output text")

    output_text = output_text.strip()
    output_text = re.sub(r"^```(?:json)?\s*|\s*```$", "", output_text, flags=re.I | re.S)
    return json.loads(output_text)


def yaml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def build_article(data: dict[str, Any], source_url: str, category: str, cta: str) -> str:
    description = str(data["description"]).strip()
    if not 60 <= len(description) <= 160:
        raise ValueError(f"description must be 60-160 characters; got {len(description)}")

    tags = [str(tag).strip() for tag in data.get("tags", []) if str(tag).strip()]
    faq = data.get("faq", [])
    related = data.get("related_links", [])

    lines = [
        "---",
        f"title: {yaml_string(str(data['title']).strip())}",
        f"description: {yaml_string(description)}",
        f"publishedAt: {date.today().isoformat()}",
        f"category: {yaml_string(str(data.get('category') or category))}",
        "tags:",
    ]
    lines.extend(f"  - {yaml_string(tag)}" for tag in tags)
    lines.extend([
        'author: "羽田野 剛士"',
        "draft: true",
        "featured: false",
        f"sourceUrl: {yaml_string(source_url)}",
        f"cta: {cta}",
        "---",
        "",
        str(data.get("summary", "")).strip(),
        "",
        str(data["body_markdown"]).strip(),
        "",
        "## よくある質問",
        "",
    ])

    for item in faq[:5]:
        lines.extend([
            f"### {str(item.get('question', '')).strip()}",
            "",
            str(item.get("answer", "")).strip(),
            "",
        ])

    if related:
        lines.extend(["## 関連情報", ""])
        for item in related:
            url = str(item.get("url", "")).strip()
            label = str(item.get("label", "")).strip()
            if url and label and any(url == allowed["url"] for allowed in ALLOWED_LINKS):
                lines.append(f"- [{label}]({url})")
        lines.append("")

    lines.extend([
        "> この記事は公開情報をもとにHDNが実務上の観点から整理したものです。個別の診療・法務・広告判断は、関係法令や専門家の確認を前提としてください。",
        "",
    ])
    return "\n".join(lines)


def write_outputs(slug: str, data: dict[str, Any], article: str) -> list[Path]:
    ARTICLE_DIR.mkdir(parents=True, exist_ok=True)
    social_path = SOCIAL_DIR / slug
    social_path.mkdir(parents=True, exist_ok=True)
    EN_DRAFT_DIR.mkdir(parents=True, exist_ok=True)

    article_path = ARTICLE_DIR / f"{slug}.md"
    article_path.write_text(article, encoding="utf-8")

    outputs = [article_path]
    social_map = {
        "x.md": data.get("social_x", ""),
        "facebook.md": data.get("social_facebook", ""),
        "linkedin.md": data.get("social_linkedin", ""),
    }
    for filename, text in social_map.items():
        path = social_path / filename
        path.write_text(str(text).strip() + "\n", encoding="utf-8")
        outputs.append(path)

    en_path = EN_DRAFT_DIR / f"{slug}.md"
    en_path.write_text(
        "\n".join([
            f"# {str(data.get('english_title', '')).strip()}",
            "",
            str(data.get("english_description", "")).strip(),
            "",
            str(data.get("english_summary", "")).strip(),
            "",
            "> English draft for editorial review. Not published automatically.",
            "",
        ]),
        encoding="utf-8",
    )
    outputs.append(en_path)
    return outputs


def main() -> int:
    args = parse_args()
    slug = validate_slug(args.slug)
    target = ARTICLE_DIR / f"{slug}.md"
    if target.exists():
        raise FileExistsError(f"Article already exists: {target}")

    source_title, source_text = fetch_source(args.url)
    data = call_openai(args.url, source_title, source_text, args.category, args.cta)
    article = build_article(data, args.url, args.category, args.cta)
    outputs = write_outputs(slug, data, article)

    print("Generated files:")
    for path in outputs:
        print(path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
