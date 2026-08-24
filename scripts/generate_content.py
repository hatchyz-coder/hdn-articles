#!/usr/bin/env python3
"""Generate quality-gated HDN JP/EN articles and social copy from a public source URL."""
from __future__ import annotations

import argparse
import json
import os
import re
import socket
import sys
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from drive_reference_context import load_reference_context

ROOT = Path(__file__).resolve().parents[1]
ARTICLE_DIR = ROOT / "src" / "content" / "articles"
EN_ARTICLE_DIR = ROOT / "src" / "content" / "articles-en"
SOCIAL_DIR = ROOT / "social"
PROMPT_PATH = ROOT / "prompts" / "article-system.md"
FINAL_QUALITY_FLOOR = 72
MIN_JP_BODY_CHARS = 1200
MIN_EN_BODY_CHARS = 900

ALLOWED_LINKS = [
    {"label": "HDN Japan", "url": "https://hdnjapan.com/"},
    {"label": "自由診療導入支援", "url": "https://hdnjapan.com/self-pay.html"},
    {"label": "LHub", "url": "https://hdnjapan.com/lhub.html"},
    {"label": "SNS・動画戦略", "url": "https://hdnjapan.com/medical-sns.html"},
    {"label": "無料相談", "url": "https://hdnjapan.com/consultation-form.html"},
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--category", default="医療経営")
    parser.add_argument("--cta", choices=["consultation", "lhub", "self-pay", "sns"], default="consultation")
    parser.add_argument("--min-score", type=int, default=FINAL_QUALITY_FLOOR)
    parser.add_argument("--publish", action="store_true")
    return parser.parse_args()


def validate_slug(slug: str) -> str:
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        raise ValueError("slug must contain lowercase letters, numbers, and hyphens only")
    return slug


def _host_is_public(host: str) -> bool:
    if not host or host.lower() == "localhost":
        return False
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    import ipaddress
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_unspecified:
            return False
    return True


def validate_public_source_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("source URL must be a public HTTP(S) URL")
    if not _host_is_public(parsed.hostname):
        raise ValueError("source URL host is not public")
    return url


def fetch_source(url: str) -> tuple[str, str]:
    validate_public_source_url(url)
    response = requests.get(url, timeout=30, headers={"User-Agent": "HDN-Content-Engine/2.0 (+https://hdnjapan.com/)"})
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    for node in soup(["script", "style", "noscript", "svg", "form", "nav", "footer"]):
        node.decompose()
    title = soup.title.get_text(" ", strip=True) if soup.title else url
    candidates = soup.select("article, main, [role=main]")
    target = max(candidates, key=lambda n: len(n.get_text(" ", strip=True)), default=soup.body or soup)
    text = "\n".join(line.strip() for line in target.get_text("\n", strip=True).splitlines() if line.strip())
    if len(text) < 300:
        raise RuntimeError("Source page text was too short to generate a reliable article")
    return title[:300], text[:30000]


def private_reference_context(source_title: str, source_text: str, category: str) -> dict[str, Any]:
    query = f"{source_title}\n{category}\n{source_text[:3000]}"
    try:
        context = load_reference_context(query)
    except Exception as exc:
        print(f"WARN: private Drive reference context unavailable ({type(exc).__name__})", file=sys.stderr)
        return {"internal_operations": [], "lhub_archive": [], "available": False}
    print(
        "Private Drive reference context: "
        f"internal={len(context.get('internal_operations', []))}, "
        f"lhub_archive={len(context.get('lhub_archive', []))}",
        file=sys.stderr,
    )
    return context


def _extract_output_text(payload: dict[str, Any]) -> str:
    output_text = payload.get("output_text")
    if output_text:
        return str(output_text)
    pieces: list[str] = []
    for item in payload.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                pieces.append(content["text"])
    return "\n".join(pieces)


def call_openai(
    source_url: str,
    source_title: str,
    source_text: str,
    category: str,
    cta: str,
    reference_context: dict[str, Any],
    quality_feedback: list[str] | None = None,
) -> dict[str, Any]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured in GitHub Actions secrets")
    instructions = PROMPT_PATH.read_text(encoding="utf-8") + """

## Mandatory final publication score
Return three additional JSON fields: `should_publish` (boolean), `editorial_score` (integer 0-100), and `skip_reason` (string).
Score the FINAL EDITED JP/EN PAIR, not the urgency or raw source. A non-breaking announcement can score highly if the finished article creates a useful, differentiated operational analysis. Score below 72 only when the final pair remains too thin, generic, unsupported, duplicative, or operationally unhelpful after serious editing. Do not inflate the score to force publication.
The article should remain useful even if the reader never buys an HDN service. Prefer a concrete operational tension, comparison, failure pattern, public evidence, decision framework, or boundary condition over generic explanation.
"""
    user_input = {
        "source_url": source_url,
        "source_title": source_title,
        "source_text": source_text,
        "requested_category": category,
        "cta_type": cta,
        "allowed_links": ALLOWED_LINKS,
        "private_editorial_reference": {
            "internal_operations": reference_context.get("internal_operations", []),
            "lhub_archive": reference_context.get("lhub_archive", []),
        },
        "quality_feedback_from_previous_attempt": quality_feedback or [],
    }
    response = requests.post(
        "https://api.openai.com/v1/responses",
        timeout=180,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": os.environ.get("OPENAI_MODEL", "gpt-5-mini"),
            "instructions": instructions,
            "input": json.dumps(user_input, ensure_ascii=False),
            "max_output_tokens": 12000,
            "store": False,
        },
    )
    response.raise_for_status()
    output_text = _extract_output_text(response.json()).strip()
    if not output_text:
        raise RuntimeError("OpenAI response did not contain output text")
    output_text = re.sub(r"^```(?:json)?\s*|\s*```$", "", output_text, flags=re.I | re.S)
    return json.loads(output_text)


def yaml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _fit_description(value: Any, fallback: Any, min_chars: int, max_chars: int, *, english: bool = False) -> str:
    text = str(value or "").strip() or str(fallback or "").strip()
    if len(text) < min_chars:
        extra = (
            " Practical implications, trade-offs, and implementation checks are explained for operators."
            if english
            else " 実務への影響、判断基準、運用時に確認したいポイントを具体的に整理します。"
        )
        text = (text + extra).strip()
    if len(text) > max_chars:
        text = text[: max_chars - 1].rstrip() + "…"
    return text


def _fit_social_title(value: Any, fallback: Any, max_chars: int) -> str:
    text = str(value or fallback or "").strip()
    if len(text) < 4:
        text = str(fallback or "HDN practical analysis").strip()
    return text[:max_chars].rstrip()


def depth_issues(data: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    required = ("title", "summary", "body_markdown", "english_title", "english_summary", "english_body_markdown")
    for key in required:
        if not str(data.get(key, "")).strip():
            issues.append(f"missing:{key}")
    jp = str(data.get("body_markdown", "")).strip()
    en = str(data.get("english_body_markdown", "")).strip()
    if jp and len(jp) < MIN_JP_BODY_CHARS:
        issues.append("jp_body_too_thin")
    if en and len(en) < MIN_EN_BODY_CHARS:
        issues.append("en_body_too_thin")
    if jp and jp.count("## ") < 2:
        issues.append("jp_structure_too_thin")
    if en and en.count("## ") < 2:
        issues.append("en_structure_too_thin")
    return issues


def final_quality_issues(data: dict[str, Any], min_score: int) -> list[str]:
    issues = depth_issues(data)
    if not bool(data.get("should_publish", True)):
        issues.append("model_should_publish_false")
    try:
        score = int(data.get("editorial_score", 0))
    except (TypeError, ValueError):
        score = 0
    if score < min_score:
        issues.append(f"editorial_score_below_{min_score}")
    return issues


def build_article(data: dict[str, Any], source_url: str, category: str, cta: str, *, publish: bool = False) -> str:
    title = str(data.get("title", "")).strip()
    description = _fit_description(data.get("description"), data.get("summary") or title, 60, 160)
    social_title = _fit_social_title(data.get("social_title"), title, 80)
    tags = [str(tag).strip() for tag in data.get("tags", []) if str(tag).strip()]
    lines = [
        "---", f"title: {yaml_string(title)}", f"socialTitle: {yaml_string(social_title)}",
        f"description: {yaml_string(description)}", f"publishedAt: {date.today().isoformat()}",
        f"category: {yaml_string(str(data.get('category') or category))}", "tags:",
        *[f"  - {yaml_string(tag)}" for tag in tags], 'author: "羽田野 剛士"',
        f"draft: {'false' if publish else 'true'}", "featured: false", f"sourceUrl: {yaml_string(source_url)}", f"cta: {cta}",
        "---", "", str(data.get("summary", "")).strip(), "", str(data.get("body_markdown", "")).strip(),
    ]
    faq = data.get("faq", [])[:5]
    if faq:
        lines.extend(["", "## よくある質問", ""])
        for item in faq:
            lines.extend([f"### {str(item.get('question', '')).strip()}", "", str(item.get("answer", "")).strip(), ""])
    related = data.get("related_links", [])
    safe_allowed = {item["url"] for item in ALLOWED_LINKS}
    safe_related = [(str(i.get("label", "")).strip(), str(i.get("url", "")).strip()) for i in related if isinstance(i, dict)]
    safe_related = [(label, url) for label, url in safe_related if label and url in safe_allowed]
    if safe_related:
        lines.extend(["## 関連情報", "", *[f"- [{label}]({url})" for label, url in safe_related], ""])
    lines.extend(["> この記事は公開情報をもとにHDNが実務上の観点から整理したものです。個別の診療・法務・広告判断は、関係法令や専門家の確認を前提としてください。", ""])
    return "\n".join(lines)


def build_english_article(data: dict[str, Any], source_url: str, category: str, cta: str, *, publish: bool = False) -> str:
    title = str(data.get("english_title", "")).strip()
    description = _fit_description(data.get("english_description"), data.get("english_summary") or title, 50, 180, english=True)
    social_title = _fit_social_title(data.get("english_social_title"), title, 100)
    tags = [str(tag).strip() for tag in data.get("english_tags", data.get("tags", [])) if str(tag).strip()]
    body = str(data.get("english_body_markdown", "")).strip()
    lines = [
        "---", f"title: {yaml_string(title)}", f"socialTitle: {yaml_string(social_title)}",
        f"description: {yaml_string(description)}", f"publishedAt: {date.today().isoformat()}",
        f"category: {yaml_string(str(data.get('english_category') or data.get('category') or category))}", "tags:",
        *[f"  - {yaml_string(tag)}" for tag in tags], 'author: "Tsuyoshi Hadano"',
        f"draft: {'false' if publish else 'true'}", f"sourceUrl: {yaml_string(source_url)}", f"cta: {cta}",
        "---", "", str(data.get("english_summary", "")).strip(), "", body,
    ]
    faq = data.get("english_faq", [])[:5]
    if faq:
        lines.extend(["", "## Frequently Asked Questions", ""])
        for item in faq:
            lines.extend([f"### {str(item.get('question', '')).strip()}", "", str(item.get("answer", "")).strip(), ""])
    lines.extend(["> This article is an HDN practical interpretation of publicly available information. Individual medical, legal, regulatory, and advertising decisions should be confirmed against applicable rules and qualified professional advice.", ""])
    return "\n".join(lines)


def write_outputs(slug: str, data: dict[str, Any], article: str, english_article: str) -> list[Path]:
    ARTICLE_DIR.mkdir(parents=True, exist_ok=True)
    EN_ARTICLE_DIR.mkdir(parents=True, exist_ok=True)
    social_path = SOCIAL_DIR / slug
    social_path.mkdir(parents=True, exist_ok=True)
    article_path = ARTICLE_DIR / f"{slug}.md"
    en_path = EN_ARTICLE_DIR / f"{slug}.md"
    if article_path.exists() or en_path.exists():
        raise FileExistsError(f"Refusing to overwrite existing article pair: {slug}")
    article_path.write_text(article, encoding="utf-8")
    en_path.write_text(english_article, encoding="utf-8")
    outputs = [article_path, en_path]
    for filename, key in {"x.md": "social_x", "facebook.md": "social_facebook", "linkedin.md": "social_linkedin"}.items():
        path = social_path / filename
        path.write_text(str(data.get(key, "")).strip() + "\n", encoding="utf-8")
        outputs.append(path)
    return outputs


def main() -> int:
    args = parse_args()
    min_score = max(FINAL_QUALITY_FLOOR, int(args.min_score))
    slug = validate_slug(args.slug)
    if (ARTICLE_DIR / f"{slug}.md").exists() or (EN_ARTICLE_DIR / f"{slug}.md").exists():
        raise FileExistsError(f"Article already exists for slug: {slug}")

    source_title, source_text = fetch_source(args.url)
    reference_context = private_reference_context(source_title, source_text, args.category)
    data = call_openai(args.url, source_title, source_text, args.category, args.cta, reference_context)
    issues = final_quality_issues(data, min_score)
    if issues:
        print(f"First editorial generation requires repair: {', '.join(issues)}", file=sys.stderr)
        data = call_openai(args.url, source_title, source_text, args.category, args.cta, reference_context, issues)
        issues = final_quality_issues(data, min_score)
    if issues:
        raise RuntimeError("Final official-source article failed editorial quality gate after rewrite: " + ", ".join(issues))

    article = build_article(data, args.url, args.category, args.cta, publish=args.publish)
    english_article = build_english_article(data, args.url, args.category, args.cta, publish=args.publish)
    outputs = write_outputs(slug, data, article, english_article)
    score = int(data.get("editorial_score", 0))
    print(f"Final editorial score: {score}/100")
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
