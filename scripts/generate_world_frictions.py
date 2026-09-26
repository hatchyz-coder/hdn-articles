#!/usr/bin/env python3
"""Autonomously research, review, and write one World Frictions publication bundle.

The command is deliberately allowed to publish nothing. A scheduled run should create an
article only when both the writer and an independent reviewer clear the configured quality
thresholds and the selected sources can be tied back to URLs returned by OpenAI web search.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import requests

ROOT = Path(__file__).resolve().parents[1]
ARTICLE_DIR = ROOT / "src" / "content" / "articles"
EN_ARTICLE_DIR = ROOT / "src" / "content" / "articles-en"
SOCIAL_DIR = ROOT / "social"
PROMPT_PATH = ROOT / "prompts" / "world-frictions-system.md"

API_URL = "https://api.openai.com/v1/responses"
DEFAULT_MODEL = "gpt-5.6-terra"
DEFAULT_SCORE_THRESHOLD = 86
DEFAULT_REVIEW_THRESHOLD = 88
JST = timezone(timedelta(hours=9))
ALLOWED_CONTENT_TYPES = {
    "news-analysis",
    "opinion",
    "case-study",
    "practical-guide",
    "regulation",
}
SOURCE_KINDS = {"primary", "research", "reporting", "commentary"}
DERIVATIVE_KEYS = {
    "note": "note.md",
    "linkedin_newsletter": "linkedin-newsletter.md",
    "linkedin_post": "linkedin.md",
    "facebook": "facebook.md",
    "x": "x.md",
    "reposts": "reposts.md",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--score-threshold", type=int, default=int(os.getenv("WORLD_FRICTIONS_SCORE_THRESHOLD", DEFAULT_SCORE_THRESHOLD)))
    parser.add_argument("--review-threshold", type=int, default=int(os.getenv("WORLD_FRICTIONS_REVIEW_THRESHOLD", DEFAULT_REVIEW_THRESHOLD)))
    parser.add_argument("--model", default=os.getenv("WORLD_FRICTIONS_MODEL") or DEFAULT_MODEL)
    return parser.parse_args()


def write_github_output(**values: Any) -> None:
    output = os.getenv("GITHUB_OUTPUT")
    if not output:
        return
    with open(output, "a", encoding="utf-8") as handle:
        for key, value in values.items():
            safe = str(value).replace("\n", " ").replace("\r", " ")
            handle.write(f"{key}={safe}\n")


def write_summary(lines: list[str]) -> None:
    path = os.getenv("GITHUB_STEP_SUMMARY")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as handle:
        handle.write("\n".join(lines).rstrip() + "\n")


def yaml_string(value: str) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def normalize_url(value: str) -> str:
    value = value.strip()
    try:
        parts = urlsplit(value)
    except ValueError:
        return value
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, parts.query, ""))


def output_text(payload: dict[str, Any]) -> str:
    direct = payload.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    pieces: list[str] = []
    for item in payload.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                pieces.append(str(content["text"]))
    return "\n".join(pieces).strip()


def parse_json_response(payload: dict[str, Any]) -> dict[str, Any]:
    text = output_text(payload)
    if not text:
        raise RuntimeError("OpenAI response did not contain output text")
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.I | re.S)
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"OpenAI response was not valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise RuntimeError("OpenAI JSON response must be an object")
    return value


def searched_urls(payload: dict[str, Any]) -> set[str]:
    urls: set[str] = set()
    for item in payload.get("output", []):
        if item.get("type") != "web_search_call":
            continue
        action = item.get("action") or {}
        for source in action.get("sources") or []:
            url = source.get("url") if isinstance(source, dict) else None
            if isinstance(url, str) and url.startswith("https://"):
                urls.add(normalize_url(url))
    return urls


def call_openai(*, model: str, instructions: str, input_text: str, max_output_tokens: int, web_search: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    request: dict[str, Any] = {
        "model": model,
        "instructions": instructions,
        "input": input_text,
        "max_output_tokens": max_output_tokens,
        "reasoning": {"effort": os.getenv("WORLD_FRICTIONS_REASONING", "medium")},
        "store": False,
    }
    if web_search:
        request.update(
            {
                "tools": [{"type": "web_search"}],
                "tool_choice": "required",
                "include": ["web_search_call.action.sources"],
            }
        )

    response = requests.post(
        API_URL,
        timeout=600,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=request,
    )
    if not response.ok:
        raise RuntimeError(f"OpenAI API failed ({response.status_code}): {response.text[:1000]}")
    payload = response.json()
    return parse_json_response(payload), payload


def parse_frontmatter(text: str) -> dict[str, str]:
    match = re.match(r"\A---\s*\n(.*?)\n---\s*\n", text, flags=re.S)
    if not match:
        return {}
    result: dict[str, str] = {}
    for line in match.group(1).splitlines():
        key, sep, value = line.partition(":")
        if not sep:
            continue
        value = value.strip().strip('"').strip("'")
        result[key.strip()] = value
    return result


def existing_world_frictions() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in sorted(ARTICLE_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        fm = parse_frontmatter(text)
        if fm.get("section") != "world-frictions" and fm.get("series") != "world-frictions":
            continue
        rows.append(
            {
                "slug": path.stem,
                "title": fm.get("title", path.stem),
                "source_url": fm.get("sourceUrl", ""),
            }
        )
    return rows


def discovery_prompt(existing: list[dict[str, str]], threshold: int) -> str:
    today = datetime.now(JST).date().isoformat()
    recent = existing[-50:]
    return json.dumps(
        {
            "task": "Scout the web and select at most one World Frictions topic. Return only a compact research brief for a separate writer.",
            "today_jst": today,
            "quality_threshold": threshold,
            "existing_articles_to_avoid": recent,
            "scouting": {
                "lookback": "Prefer developments from the last 14 days, but allow an older fact only when a current development creates a genuinely new angle.",
                "domains": [
                    "work and management",
                    "AI and technology",
                    "advertising, platforms and dark patterns",
                    "healthcare systems and information asymmetry",
                    "government and institutions",
                    "cities, infrastructure and culture",
                    "consumer behavior and power imbalance",
                ],
                "candidate_count": "Search broadly enough to compare at least 6 plausible topics before choosing one.",
            },
            "selection_rules": [
                "Choose a topic many readers can recognize as an 'are?' moment, not a niche press-release summary.",
                "There must be a meaningful gap between stated purpose and observed reality, or a structural power/information/incentive mismatch.",
                "The topic must support a deeper structural explanation, not only outrage.",
                "Use at least 3 distinct credible sources, with at least one primary source or peer-reviewed/research source.",
                "Prefer primary sources and research; use high-quality reporting for context. Social posts can only be illustrative examples.",
                "Do not publish a rumor, unverified accusation, personality attack, partisan advocacy, or a topic whose central claim depends on anonymous allegations.",
                "Avoid duplicating existing World Frictions articles in topic, thesis, main source, or framing.",
                f"If no candidate honestly deserves {threshold}/100 or higher, return publish=false. Never publish filler to satisfy the schedule.",
            ],
            "score_dimensions": {
                "relatable_discomfort": 20,
                "purpose_reality_gap": 15,
                "structural_depth": 20,
                "source_strength": 20,
                "originality_vs_existing": 15,
                "cross_channel_readability": 10,
            },
            "output_contract": {
                "publish": "boolean",
                "score": "integer 0-100",
                "slug": "lowercase ASCII words separated by hyphens; blank if publish=false",
                "selection_reason": "short Japanese explanation",
                "thesis": "one-sentence Japanese thesis",
                "angle": "compact structural explanation",
                "verified_facts": "3-8 concise facts with supporting source URLs",
                "sources": "3-6 items of {title,url,kind,note}; kind is primary, research, reporting, or commentary",
            },
            "hard_rules": [
                "Facts, allegations, inference and opinion must be clearly distinguished.",
                "Do not fabricate first-hand experience, quotes, numbers, sources, URLs or research findings.",
                "Do not use Markdown asterisk emphasis anywhere.",
                "The canonical article must explain why the issue matters and its underlying structure.",
                "The ending should leave the reader with a question, self-reflection, or concrete judgment criterion rather than a generic summary.",
                "Return raw JSON only, no Markdown code fence.",
            ],
        },
        ensure_ascii=False,
    )


def writer_prompt(brief: dict[str, Any]) -> str:
    return json.dumps(
        {
            "task": "Write the Japanese and English canonical World Frictions articles from this verified research brief. Do not add facts outside it.",
            "brief": brief,
            "output": {
                "canonical": {
                    "title": "Japanese title beginning with 【",
                    "social_title": "4-80 Japanese characters",
                    "description": "60-160 Japanese characters",
                    "category": "世界の違和感",
                    "tags": "3-6 short tags",
                    "content_type": "news-analysis, opinion, case-study, practical-guide, or regulation",
                    "summary": "short Japanese lead",
                    "body_markdown": "2200-4500 Japanese characters; no source list",
                    "sources": "copy the brief source set exactly",
                },
                "english_canonical": {
                    "title": "natural English title",
                    "social_title": "4-100 characters",
                    "description": "50-180 characters",
                    "category": "World Frictions",
                    "tags": "3-6 English tags",
                    "summary": "short English lead",
                    "body_markdown": "at least 1500 characters; faithful adaptation",
                    "sources": "same URLs and kinds as the brief",
                },
            },
            "rules": ["Return raw JSON only", "No Markdown asterisk emphasis", "Distinguish fact, inference, and opinion", "Do not fabricate personal experience"],
        }, ensure_ascii=False,
    )


def derivative_prompt(canonical: dict[str, Any], english: dict[str, Any], sources: list[dict[str, str]]) -> str:
    return json.dumps(
        {
            "task": "Create channel-specific derivatives from the supplied final article only.",
            "article": {
                "title": canonical.get("title"),
                "summary": canonical.get("summary"),
                "body_markdown": canonical.get("body_markdown"),
                "english_title": english.get("title"),
                "sources": sources,
            },
            "output": {
                "note": "Japanese long-form adaptation ending with {{CANONICAL_URL}}",
                "linkedin_newsletter": "professional Japanese adaptation plus short English summary and {{CANONICAL_URL}}",
                "linkedin_post": "Japanese then English follows below. then English; include {{CANONICAL_URL}}",
                "facebook": "1200-1500 Japanese characters, starts with 【】, standalone, human voice, include {{CANONICAL_URL}}",
                "x": "concise Japanese hook with {{CANONICAL_URL}}",
                "reposts": "array of at least 3 distinct Japanese recut angles",
            },
            "rules": ["Return raw JSON only", "No Markdown asterisk emphasis", "Do not introduce new facts"],
        }, ensure_ascii=False,
    )


def validate_sources(sources: Any, retrieved: set[str]) -> tuple[list[dict[str, str]], int]:
    if not isinstance(sources, list):
        raise ValueError("canonical.sources must be an array")
    cleaned: list[dict[str, str]] = []
    seen: set[str] = set()
    matched = 0
    for item in sources:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        url = str(item.get("url", "")).strip()
        kind = str(item.get("kind", "reporting")).strip().lower()
        if not title or not url.startswith("https://") or kind not in SOURCE_KINDS:
            continue
        normalized = normalize_url(url)
        if normalized in seen:
            continue
        seen.add(normalized)
        if normalized in retrieved:
            matched += 1
        cleaned.append({"title": title, "url": url, "kind": kind})
    if len(cleaned) < 3:
        raise ValueError("World Frictions requires at least three distinct HTTPS sources")
    if not any(item["kind"] in {"primary", "research"} for item in cleaned):
        raise ValueError("World Frictions requires at least one primary or research source")
    if retrieved and matched < 2:
        raise ValueError(f"Only {matched} selected sources matched URLs returned by web search")
    return cleaned, matched


def validate_copy_block(value: Any, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} is empty")
    if "**" in text:
        raise ValueError(f"Markdown asterisk emphasis is not allowed in {name}")
    return text


def check_duplicate(candidate: dict[str, Any], existing: list[dict[str, str]], sources: list[dict[str, str]]) -> None:
    slug = str(candidate.get("slug", "")).strip()
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        raise ValueError("slug is invalid")
    if (ARTICLE_DIR / f"{slug}.md").exists() or (EN_ARTICLE_DIR / f"{slug}.md").exists():
        raise ValueError(f"slug already exists: {slug}")

    title = str((candidate.get("canonical") or {}).get("title", "")).strip()
    normalized_sources = {normalize_url(item["url"]) for item in sources}
    for row in existing:
        if SequenceMatcher(None, title, row.get("title", "")).ratio() >= 0.78:
            raise ValueError(f"topic/title is too similar to existing article: {row.get('slug')}")
        old_url = row.get("source_url", "")
        if old_url and normalize_url(old_url) in normalized_sources:
            raise ValueError(f"primary source overlaps existing World Frictions article: {row.get('slug')}")


def validate_candidate(candidate: dict[str, Any], *, threshold: int, existing: list[dict[str, str]], retrieved: set[str]) -> tuple[list[dict[str, str]], int]:
    if candidate.get("publish") is not True:
        raise ValueError("candidate is not marked for publication")
    score = int(candidate.get("score", 0))
    if score < threshold:
        raise ValueError(f"writer score {score} is below threshold {threshold}")

    canonical = candidate.get("canonical")
    english = candidate.get("english_canonical")
    if not isinstance(canonical, dict) or not isinstance(english, dict):
        raise ValueError("canonical and english_canonical objects are required")

    title = validate_copy_block(canonical.get("title"), "canonical.title")
    if not title.startswith("【"):
        raise ValueError("Japanese World Frictions title must begin with 【")
    social_title = validate_copy_block(canonical.get("social_title"), "canonical.social_title")
    description = validate_copy_block(canonical.get("description"), "canonical.description")
    if not 4 <= len(social_title) <= 80:
        raise ValueError("Japanese social_title must be 4-80 characters")
    if not 60 <= len(description) <= 160:
        raise ValueError("Japanese description must be 60-160 characters")
    body = validate_copy_block(canonical.get("body_markdown"), "canonical.body_markdown")
    if len(body) < 2200:
        raise ValueError(f"Japanese body is too short ({len(body)} characters)")
    content_type = str(canonical.get("content_type", "")).strip()
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise ValueError(f"invalid content_type: {content_type}")

    en_social = validate_copy_block(english.get("social_title"), "english_canonical.social_title")
    en_description = validate_copy_block(english.get("description"), "english_canonical.description")
    if not 4 <= len(en_social) <= 100:
        raise ValueError("English social_title must be 4-100 characters")
    if not 50 <= len(en_description) <= 180:
        raise ValueError("English description must be 50-180 characters")
    en_body = validate_copy_block(english.get("body_markdown"), "english_canonical.body_markdown")
    if len(en_body) < 1500:
        raise ValueError(f"English body is too short ({len(en_body)} characters)")

    sources, matched = validate_sources(canonical.get("sources"), retrieved)
    validate_sources(english.get("sources"), retrieved)
    check_duplicate(candidate, existing, sources)

    for key in DERIVATIVE_KEYS:
        value = candidate.get(key)
        if key == "reposts":
            if not isinstance(value, list) or len([x for x in value if str(x).strip()]) < 3:
                raise ValueError("reposts must contain at least three angles")
            for item in value:
                validate_copy_block(item, "reposts")
        else:
            text = validate_copy_block(value, key)
            if key == "facebook":
                if not text.startswith("【"):
                    raise ValueError("facebook must begin with a Japanese title in 【】")
                if not 1200 <= len(text) <= 1500:
                    raise ValueError(f"facebook must be 1200-1500 characters; got {len(text)}")
    return sources, matched


def review_prompt(candidate: dict[str, Any], existing: list[dict[str, str]], threshold: int) -> str:
    return json.dumps(
        {
            "task": "Act as an independent fact-checking and editorial review desk. Search the web again and decide whether this World Frictions draft is safe and strong enough for fully automatic publication without human review.",
            "candidate": {
                "slug": candidate.get("slug"),
                "canonical": candidate.get("canonical"),
                "english_canonical": candidate.get("english_canonical"),
            },
            "existing_articles": existing[-50:],
            "minimum_overall_score": threshold,
            "reject_if": [
                "a central factual claim is unsupported, exaggerated or contradicted by a credible source",
                "the draft treats an allegation, anonymous anecdote or inference as established fact",
                "source quality is weak or the source set does not support the thesis",
                "the topic substantially duplicates an existing World Frictions article",
                "the piece presents avoidable defamation, privacy, medical-advertising, pharmaceutical-advertising, consumer-protection or other legal/reputational risk",
                "the headline overclaims what the evidence supports",
                "the Japanese and English versions materially diverge on facts",
                "the article is mostly news summary and lacks a structural insight",
            ],
            "output": {
                "pass": "boolean",
                "overall_score": "0-100",
                "factual_confidence": "0-100",
                "source_quality": "0-100",
                "novelty": "0-100",
                "reputational_risk": "0-100 where lower is safer",
                "reason": "short Japanese explanation",
                "issues": "array of concrete issues; empty when pass=true",
            },
            "rules": [
                "Do not rewrite the article. Review it independently.",
                "Use fresh web search to verify its central claims and source credibility.",
                "Return raw JSON only.",
            ],
        },
        ensure_ascii=False,
    )


def validate_review(review: dict[str, Any], threshold: int) -> None:
    if review.get("pass") is not True:
        raise ValueError(f"independent review rejected publication: {review.get('reason', '')}")
    overall = int(review.get("overall_score", 0))
    factual = int(review.get("factual_confidence", 0))
    source_quality = int(review.get("source_quality", 0))
    novelty = int(review.get("novelty", 0))
    risk = int(review.get("reputational_risk", 100))
    if overall < threshold:
        raise ValueError(f"review score {overall} is below {threshold}")
    if factual < 90:
        raise ValueError(f"factual confidence {factual} is below 90")
    if source_quality < 85:
        raise ValueError(f"source quality {source_quality} is below 85")
    if novelty < 75:
        raise ValueError(f"novelty {novelty} is below 75")
    if risk > 20:
        raise ValueError(f"reputational risk {risk} is above 20")


def source_lines(sources: list[dict[str, str]]) -> list[str]:
    lines: list[str] = []
    for source in sources:
        lines.extend([f"- {source['title']}", f"  {source['url']}"])
    return lines


def article_markdown(data: dict[str, Any], *, slug: str, sources: list[dict[str, str]], english: bool) -> str:
    today = datetime.now(JST).date().isoformat()
    title = str(data["title"]).strip()
    social_title = str(data["social_title"]).strip()
    description = str(data["description"]).strip()
    category = str(data.get("category") or ("World Frictions" if english else "世界の違和感")).strip()
    tags = [str(tag).strip() for tag in data.get("tags", []) if str(tag).strip()][:6]
    summary = str(data.get("summary", "")).strip()
    body = str(data["body_markdown"]).strip()
    content_type = str(data.get("content_type") or "news-analysis").strip()
    if content_type not in ALLOWED_CONTENT_TYPES:
        content_type = "news-analysis"
    author = "Tsuyoshi Hadano" if english else "羽田野 剛士"
    heading = "## Sources and references" if english else "## 出典・一次情報・参考文献"
    strongest_url = sources[0]["url"]

    lines = [
        "---",
        f"title: {yaml_string(title)}",
        f"socialTitle: {yaml_string(social_title)}",
        f"description: {yaml_string(description)}",
        f"publishedAt: {today}",
        f"category: {yaml_string(category)}",
        "tags:",
    ]
    lines.extend(f"  - {yaml_string(tag)}" for tag in tags)
    lines.extend(
        [
            f"author: {yaml_string(author)}",
            "draft: false",
            "featured: false",
            f"sourceUrl: {yaml_string(strongest_url)}",
            "cta: editorial",
            "audiences:",
            '  - "general"',
            'section: "world-frictions"',
            'industry: "other"',
            'series: "world-frictions"',
            f'contentType: "{content_type}"',
            "---",
            "",
            summary,
            "",
            body,
            "",
            heading,
            "",
            *source_lines(sources),
            "",
        ]
    )
    text = "\n".join(lines)
    if "**" in text:
        raise ValueError("generated article contains Markdown asterisk emphasis")
    return text


def derivative_text(value: Any, canonical_url: str, *, reposts: bool = False) -> str:
    if reposts:
        items = [str(item).strip() for item in value if str(item).strip()]
        return "\n".join(f"- {item}" for item in items) + "\n"
    text = str(value).strip().replace("{{CANONICAL_URL}}", canonical_url)
    if canonical_url not in text:
        text = text.rstrip() + f"\n\n{canonical_url}\n"
    if "**" in text:
        raise ValueError("distribution copy contains Markdown asterisk emphasis")
    return text.rstrip() + "\n"


def write_bundle(candidate: dict[str, Any], sources: list[dict[str, str]]) -> tuple[str, list[Path]]:
    slug = str(candidate["slug"]).strip()
    canonical = candidate["canonical"]
    english = candidate["english_canonical"]
    en_sources_raw = english.get("sources") or sources
    en_sources = [
        {"title": str(item.get("title", "")).strip(), "url": str(item.get("url", "")).strip(), "kind": str(item.get("kind", "reporting"))}
        for item in en_sources_raw
        if isinstance(item, dict) and str(item.get("url", "")).startswith("https://")
    ]
    if len(en_sources) < 3:
        en_sources = sources

    jp_path = ARTICLE_DIR / f"{slug}.md"
    en_path = EN_ARTICLE_DIR / f"{slug}.md"
    social_dir = SOCIAL_DIR / slug
    social_dir.mkdir(parents=True, exist_ok=False)
    jp_path.write_text(article_markdown(canonical, slug=slug, sources=sources, english=False), encoding="utf-8")
    en_path.write_text(article_markdown(english, slug=slug, sources=en_sources, english=True), encoding="utf-8")

    canonical_url = f"https://article.hdnjapan.com/articles/{slug}/"
    written = [jp_path, en_path]
    for key, filename in DERIVATIVE_KEYS.items():
        path = social_dir / filename
        path.write_text(derivative_text(candidate[key], canonical_url, reposts=(key == "reposts")), encoding="utf-8")
        written.append(path)
    return canonical_url, written


def main() -> int:
    args = parse_args()
    existing = existing_world_frictions()
    base_instructions = PROMPT_PATH.read_text(encoding="utf-8")
    instructions = base_instructions + "\n\nAUTOMATION ADDENDUM\nYou are running without human editorial approval. Be more conservative, not less. If evidence or novelty is marginal, return publish=false."

    brief, discovery_payload = call_openai(
        model=args.model,
        instructions=instructions,
        input_text=discovery_prompt(existing, args.score_threshold),
        max_output_tokens=1800,
        web_search=True,
    )

    if brief.get("publish") is not True:
        reason = str(brief.get("selection_reason") or "No candidate cleared the editorial threshold.").strip()
        write_github_output(publish="false", reason=reason, score=int(brief.get("score", 0) or 0))
        write_summary(["## World Frictions", "", "No article was published.", "", f"Reason: {reason}"])
        print(f"SKIP: {reason}")
        return 0

    retrieved = searched_urls(discovery_payload)
    try:
        brief_sources, _ = validate_sources(brief.get("sources"), retrieved)
    except Exception as exc:
        reason = f"Discovery output failed source gate: {exc}"
        write_github_output(publish="false", reason=reason, score=int(brief.get("score", 0) or 0))
        write_summary(["## World Frictions", "", "No article was published.", "", reason])
        print(f"SKIP: {reason}")
        return 0

    written, _writer_payload = call_openai(
        model=args.model,
        instructions=instructions,
        input_text=writer_prompt({**brief, "sources": brief_sources}),
        max_output_tokens=5000,
        web_search=False,
    )
    canonical = written.get("canonical")
    english = written.get("english_canonical")
    if not isinstance(canonical, dict) or not isinstance(english, dict):
        raise RuntimeError("Writer response must contain canonical and english_canonical")
    derivatives, _derivative_payload = call_openai(
        model=args.model,
        instructions=instructions,
        input_text=derivative_prompt(canonical, english, brief_sources),
        max_output_tokens=3800,
        web_search=False,
    )
    candidate = {
        **brief,
        "canonical": {**canonical, "sources": brief_sources},
        "english_canonical": {**english, "sources": brief_sources},
        **derivatives,
    }
    try:
        sources, matched = validate_candidate(candidate, threshold=args.score_threshold, existing=existing, retrieved=retrieved)
    except Exception as exc:
        reason = f"Writer output failed deterministic gate: {exc}"
        write_github_output(publish="false", reason=reason, score=int(candidate.get("score", 0) or 0))
        write_summary(["## World Frictions", "", "No article was published.", "", reason])
        print(f"SKIP: {reason}")
        return 0

    reviewer_instructions = (
        "You are the independent review desk for HDN's World Frictions editorial series. "
        "Your role is to prevent automated publication of weak, misleading, repetitive, defamatory, or poorly sourced work. "
        "Be conservative and return JSON only."
    )
    review, _review_payload = call_openai(
        model=args.model,
        instructions=reviewer_instructions,
        input_text=review_prompt(candidate, existing, args.review_threshold),
        max_output_tokens=1800,
        web_search=True,
    )
    try:
        validate_review(review, args.review_threshold)
    except Exception as exc:
        reason = f"Independent review gate rejected publication: {exc}"
        write_github_output(publish="false", reason=reason, score=int(candidate.get("score", 0) or 0))
        write_summary(["## World Frictions", "", "No article was published.", "", reason, "", f"Reviewer: {review.get('reason', '')}"])
        print(f"SKIP: {reason}")
        return 0

    canonical_url, written = write_bundle(candidate, sources)
    slug = str(candidate["slug"])
    score = int(candidate.get("score", 0))
    review_score = int(review.get("overall_score", 0))
    reason = str(candidate.get("selection_reason", "")).strip()
    write_github_output(
        publish="true",
        slug=slug,
        score=score,
        review_score=review_score,
        title=str(candidate["canonical"]["title"]).strip(),
        canonical_url=canonical_url,
        reason=reason,
    )
    write_summary(
        [
            "## World Frictions candidate passed",
            "",
            f"- Slug: `{slug}`",
            f"- Writer score: {score}",
            f"- Independent review: {review_score}",
            f"- Search-grounded selected sources matched: {matched}/{len(sources)}",
            f"- Canonical URL after deploy: {canonical_url}",
            f"- Selection: {reason}",
            "",
            "Generated files:",
            *[f"- `{path.relative_to(ROOT)}`" for path in written],
        ]
    )
    print(json.dumps({"publish": True, "slug": slug, "score": score, "review_score": review_score, "canonical_url": canonical_url}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
