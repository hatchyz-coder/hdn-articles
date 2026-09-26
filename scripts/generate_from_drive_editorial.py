#!/usr/bin/env python3
"""Generate one publication-ready JP/EN article from the approved Drive draft pool.

The Drive document is treated as an editorial seed, not a factual source. Current public
web information is researched during generation and private Drive identifiers are never
written into public article assets.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

import requests

import generate_from_drive_knowledge as base

ROOT = Path(__file__).resolve().parents[1]
PROMPT_PATH = ROOT / "prompts" / "drive-editorial-daily.md"
EN_ARTICLE_DIR = ROOT / "src" / "content" / "articles-en"
MAX_SCAN = 500
DEFAULT_GROQ_MODEL = "groq/compound"
DEFAULT_GROQ_FALLBACK_MODEL = "openai/gpt-oss-120b"
PROVIDER_REJECTION_STATUSES = {400, 404, 422}

# Fingerprint of the approved Drive editorial folder. The raw private folder ID is never
# committed to this public repository, while a misconfigured Actions variable fails closed.
EXPECTED_FOLDER_FINGERPRINT = "377cdda8bba3afb0cbf97915b88d8afb46a313417c07b2885cae8c3b76997bc0"

# Kept for diagnostics/backwards compatibility only. Daily selection is intentionally
# queue-based now: every eligible draft in the approved folder must eventually be consumed.
KEYWORD_WEIGHTS = {
    "クリニック": 10,
    "医療": 9,
    "病院": 8,
    "歯科": 8,
    "診療": 9,
    "自由診療": 12,
    "オンライン診療": 12,
    "患者": 10,
    "LINE": 10,
    "LHub": 12,
    "予約": 7,
    "問診": 8,
    "決済": 7,
    "集患": 7,
    "医療広告": 10,
    "薬機法": 10,
    "景表法": 10,
    "SNS": 7,
    "YouTube": 7,
    "動画": 6,
    "経営": 6,
    "DX": 5,
    "業務改善": 7,
    "CRM": 7,
}
OFF_BRAND = {
    "NFT", "仮想通貨", "暗号資産", "占い", "競馬", "パチンコ", "カジノ",
    "CBD", "大麻", "VAPE", "電子タバコ", "アダルト", "風俗",
}


def _state_key(doc_id: str) -> str:
    return hashlib.sha256(doc_id.encode("utf-8")).hexdigest()


def _record(state: dict[str, Any], doc_id: str) -> dict[str, Any]:
    return state.setdefault("documents", {}).setdefault(_state_key(doc_id), {})


def document_record(state: dict[str, Any], doc_id: str) -> dict[str, Any]:
    return _record(state, doc_id)


def is_unprocessed_or_updated(state: dict[str, Any], doc: dict[str, Any]) -> bool:
    record = state.get("documents", {}).get(_state_key(doc["id"]))
    if not record:
        return True
    if record.get("status") in {"processing", "api_timeout", "os_timeout", "dry_run"} and int(record.get("retry_count", 0)) <= base.MAX_RETRIES:
        return True
    return record.get("modifiedTime") != doc.get("modifiedTime")


def mark_started(state: dict[str, Any], doc: dict[str, Any]) -> None:
    record = _record(state, doc["id"])
    record.update({
        "modifiedTime": doc.get("modifiedTime"),
        "status": "processing",
        "startedAt": base.now_iso(),
        "retry_count": int(record.get("retry_count", 0)),
    })
    state["updatedAt"] = base.now_iso()


def mark_finished(state: dict[str, Any], doc: dict[str, Any], status: str, detail: dict[str, Any], permanent: bool) -> None:
    record = _record(state, doc["id"])
    retry = int(record.get("retry_count", 0)) + (0 if permanent else 1)
    # Keep only operational, non-identifying details on the public state branch.
    safe_detail = {k: v for k, v in detail.items() if k in {"reason", "score", "slug", "manualReview", "sourceProcessing"}}
    record.update({
        "modifiedTime": doc.get("modifiedTime"),
        "status": status,
        "finishedAt": base.now_iso(),
        "retry_count": retry,
        **safe_detail,
    })
    state["updatedAt"] = base.now_iso()


def relevance_score(name: str) -> int:
    """Diagnostic-only legacy score; it no longer controls queue eligibility."""
    upper = name.upper()
    if any(term.upper() in upper for term in OFF_BRAND):
        return -100
    return sum(weight for term, weight in KEYWORD_WEIGHTS.items() if term.upper() in upper)


def is_marked_published(name: str) -> bool:
    """Return True only for explicit publication markers, never for words like 決済."""
    normalized = str(name).replace("　", " ")
    patterns = (
        r"(?:^|[\s_\-])済(?:$|[\s_\-])",
        r"[（(]\s*(?:\d{6})?済\s*[）)]",
    )
    return any(re.search(pattern, normalized) for pattern in patterns)


def queue_sort_key(doc: dict[str, Any]) -> tuple[Any, ...]:
    """Consume LH/article-number drafts first, then other drafts oldest-first."""
    name = str(doc.get("name", ""))
    match = re.search(r"LH\s*(\d+)\s*_\s*記事\s*(\d+)", name, re.I)
    if match:
        return (0, int(match.group(1)), int(match.group(2)), name)
    return (1, str(doc.get("modifiedTime", "")), name)


def _verify_approved_folder(folder_id: str) -> None:
    fingerprint = hashlib.sha256(folder_id.encode("utf-8")).hexdigest()
    if fingerprint != EXPECTED_FOLDER_FINGERPRINT:
        raise RuntimeError("Configured Drive editorial folder does not match the approved daily queue")


def select_target_doc(drive: Any, state: dict[str, Any], folder_id: str, args: Any, timer: Any):
    with timer.section("driveSeconds", "Drive select editorial seed"):
        _verify_approved_folder(folder_id)
        source_folder = drive.files().get(
            fileId=folder_id,
            fields="id,name,mimeType,parents",
            supportsAllDrives=True,
        ).execute()
        if source_folder.get("mimeType") != base.FOLDER_MIME:
            raise RuntimeError("Configured Drive editorial source must be a folder")

        if args.document_id:
            doc = base.get_doc_metadata(drive, args.document_id)
            if not base.document_is_within_scope(drive, doc, folder_id):
                raise RuntimeError("Manual document_id is outside the approved editorial source folder")
            if is_marked_published(str(doc.get("name", ""))):
                raise RuntimeError("Manual document_id is explicitly marked as already published")
            timer.metrics["driveFetched"] = 1
            return doc, "manual_document_id"

        docs, _folders = base.list_recent_seed_docs(drive, folder_id, MAX_SCAN)
        timer.metrics["driveFetched"] = len(docs)
        candidates = [
            doc for doc in docs
            if is_unprocessed_or_updated(state, doc)
            and not is_marked_published(str(doc.get("name", "")))
        ]
        timer.metrics["newDocuments"] = len(candidates)
        candidates.sort(key=queue_sort_key)
        return (candidates[0], "daily_backlog_queue") if candidates else (None, "daily_backlog_queue")


def _groq_models() -> list[str]:
    """Return a de-duplicated primary/fallback model chain.

    Repository variables may retain a provider model that later becomes unavailable.
    Keeping the fallback in code prevents one stale variable from stopping publication.
    """
    configured = [
        os.environ.get("HDN_GROQ_MODEL", DEFAULT_GROQ_MODEL).strip(),
        os.environ.get("HDN_GROQ_FALLBACK_MODEL", DEFAULT_GROQ_FALLBACK_MODEL).strip(),
    ]
    return list(dict.fromkeys(model for model in configured if model))


def _groq_request_body(model: str, instructions: str, payload_input: str) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": instructions},
            {"role": "user", "content": (
                "Use actual current public web research and return a single JSON object. "
                "Do not invent citations or URLs.\n\n" + payload_input
            )},
        ],
        "max_completion_tokens": 6000,
    }
    if model.startswith("groq/compound"):
        # Compound performs its own tool orchestration. Keep the provider's documented
        # minimal request shape; response_format/compound_custom combinations have been
        # rejected by the provider even while the model itself remains listed.
        return body

    if model.startswith("openai/gpt-oss-"):
        # Groq's documented built-in browser-search example does not combine the
        # tool with response_format. The provider rejects that combination with
        # invalid_request_error, so keep the JSON-only requirement in the prompt.
        body["tools"] = [{"type": "browser_search"}]
        return body
    body["response_format"] = {"type": "json_object"}
    return body


def _provider_error_code(response: Any) -> str:
    """Extract a non-sensitive provider error code for diagnostics."""
    try:
        error = response.json().get("error") or {}
    except (TypeError, ValueError, AttributeError):
        return "unknown"
    code = str(error.get("code") or error.get("type") or "unknown")
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", code)[:80] or "unknown"


def call_openai_once(doc: dict[str, Any], source_text: str, source_processing: dict[str, Any], timer: Any, mock_timeout: bool) -> dict[str, Any]:
    instructions = PROMPT_PATH.read_text(encoding="utf-8")
    user_input = {
        "today": date.today().isoformat(),
        "seed_title": doc.get("name"),
        "seed_text": source_text,
        "source_processing": source_processing,
        "allowed_links": base.ALLOWED_LINKS,
        "existing_article_titles": _existing_titles(),
        "editorial_goal": "Use the private draft only as a seed. Research current public news/trends and rebuild the article for HDN's current audience.",
    }
    payload_input = json.dumps(user_input, ensure_ascii=False)
    timer.metrics["apiCalls"] = 1
    timer.metrics["aiEvaluations"] = 1
    timer.metrics["inputCharacters"] = len(payload_input) + len(instructions)
    if mock_timeout:
        raise TimeoutError("OpenAI mock timed out")
    # Groq-first: preserve the existing JSON contract and editorial quality gates.
    # No unbudgeted OpenAI fallback: failures leave the source eligible for later retry.
    groq_key = os.environ.get("GROQ_API_KEY")
    if not groq_key:
        base.write_output("selected", "false")
        base.write_output("reason", "api_unconfigured")
        raise RuntimeError("GROQ_API_KEY is not configured; no paid fallback attempted")
    with timer.section("openaiSeconds", "Groq editorial generation with web research"):
        models = _groq_models()
        response = None
        for index, model in enumerate(models):
            try:
                response = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    timeout=(10, 90),
                    headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
                    json=_groq_request_body(model, instructions, payload_input),
                )
            except requests.Timeout as exc:
                raise TimeoutError("Groq API timed out during editorial generation") from exc

            if response.status_code == 429:
                # The slot must stop without repeatedly spending the provider's limited quota.
                # Preserve the draft and let the next scheduled slot check availability again.
                base.write_output("selected", "false")
                base.write_output("reason", "api_rate_limited")
                raise RuntimeError("Groq API HTTP 429 (api_rate_limited); defer until next scheduled slot")

            has_fallback = index + 1 < len(models)
            if response.status_code in PROVIDER_REJECTION_STATUSES and has_fallback:
                print(
                    "Groq provider rejected editorial model "
                    f"model={model} status={response.status_code} code={_provider_error_code(response)}; "
                    f"falling back to {models[index + 1]}",
                    file=sys.stderr,
                    flush=True,
                )
                continue
            break

    if response is None:
        base.write_output("selected", "false")
        base.write_output("reason", "api_model_unavailable")
        raise RuntimeError("No Groq editorial model is configured")
    if response.status_code in PROVIDER_REJECTION_STATUSES:
        base.write_output("selected", "false")
        base.write_output("reason", "api_model_unavailable")
        raise RuntimeError(
            "Groq editorial models rejected the request "
            f"(status={response.status_code}, code={_provider_error_code(response)})"
        )
    response.raise_for_status()
    choices = response.json().get("choices") or []
    if not choices:
        raise RuntimeError("Groq API returned no choices; retain article for retry")
    payload = {"output_text": (choices[0].get("message") or {}).get("content") or ""}
    output_text = payload.get("output_text", "")
    if not output_text:
        chunks: list[str] = []
        for item in payload.get("output", []):
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    chunks.append(content.get("text", ""))
        output_text = "\n".join(chunks)
    output_text = re.sub(r"^```(?:json)?\s*|\s*```$", "", output_text.strip(), flags=re.I | re.S)
    return json.loads(output_text)


def _existing_titles() -> list[str]:
    titles: list[str] = []
    pattern = re.compile(r'^title:\s*["\']?(.*?)["\']?\s*$', re.MULTILINE)
    for path in sorted(base.ARTICLE_DIR.glob("*.md")):
        match = pattern.search(path.read_text(encoding="utf-8"))
        if match:
            titles.append(match.group(1))
    return titles[-100:]


def _safe_refs(data: dict[str, Any]) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    for item in data.get("references", [])[:12]:
        label = str(item.get("label", "")).strip()
        url = str(item.get("url", "")).strip()
        if label and re.match(r"^https?://", url):
            refs.append({"label": label, "url": url})
    return refs


def _cta(data: dict[str, Any]) -> str:
    value = str(data.get("cta", "consultation")).strip()
    return value if value in {"consultation", "lhub", "self-pay", "sns"} else "consultation"


def _fit_description(value: Any, minimum: int, maximum: int, label: str) -> str:
    """Normalize a generated meta description without spending another model call."""
    description = re.sub(r"\s+", " ", str(value)).strip()
    if len(description) < minimum:
        raise ValueError(f"{label} must be {minimum}-{maximum} characters; got {len(description)}")
    if len(description) <= maximum:
        return description

    clipped = description[: maximum - 1].rstrip()
    # Avoid leaving a visibly partial English word when a nearby word boundary exists.
    if " " in clipped:
        at_boundary = clipped.rsplit(" ", 1)[0].rstrip(" ,;:-")
        if len(at_boundary) >= minimum:
            clipped = at_boundary
    return clipped + "…"


def _article_taxonomy(data: dict[str, Any]) -> tuple[list[str], str]:
    """Classify the fixed LHub lane into schema-safe audience and industry values."""
    text = " ".join(
        str(value)
        for value in (
            data.get("title", ""),
            data.get("english_title", ""),
            data.get("category", ""),
            " ".join(str(tag) for tag in data.get("tags", [])),
        )
    ).lower()
    classifiers = (
        ("dental", ("歯科", "歯医者", "dental")),
        ("medical", ("クリニック", "診療", "患者", "医療", "clinic", "medical", "patient")),
        ("real-estate", ("不動産", "賃貸", "物件", "古民家", "real estate", "rental", "property")),
        ("retail", ("小売", "店舗", "物販", "ec", "通販", "retail", "commerce", "shop")),
        ("creator", ("クリエイター", "声優", "ファンクラブ", "creator", "artist", "fan club")),
        ("fortune", ("占い", "鑑定", "fortune", "astrology")),
    )
    industry = next(
        (name for name, keywords in classifiers if any(keyword in text for keyword in keywords)),
        "other",
    )
    audiences = ["clinic", "lhub"] if industry in {"medical", "dental"} else ["lhub"]
    return audiences, industry


def build_article(data: dict[str, Any], doc: dict[str, Any]) -> str:
    description = _fit_description(data["description"], 60, 160, "description")
    tags = [str(tag).strip() for tag in data.get("tags", []) if str(tag).strip()]
    audiences, industry = _article_taxonomy(data)
    today = date.today().isoformat()
    lines = [
        "---",
        f"title: {base.yaml_string(str(data['title']).strip())}",
        f"description: {base.yaml_string(description)}",
        f"publishedAt: {today}",
        f"updatedAt: {today}",
        f"category: {base.yaml_string(str(data.get('category') or 'クリニック経営'))}",
        "tags:",
        *[f"  - {base.yaml_string(tag)}" for tag in tags],
        'author: "羽田野 剛士"',
        "draft: false",
        "featured: false",
        f"cta: {_cta(data)}",
        "audiences:",
        *[f'  - "{audience}"' for audience in audiences],
        'section: "lhub-usecase"',
        f'industry: "{industry}"',
        'series: "lhub-use-cases"',
        'contentType: "practical-guide"',
        "---",
        "",
        str(data.get("summary", "")).strip(),
        "",
        str(data["body_markdown"]).strip(),
    ]
    faq = data.get("faq", [])[:5]
    if faq:
        lines.extend(["", "## よくある質問", ""])
        for item in faq:
            lines.extend([f"### {str(item.get('question', '')).strip()}", "", str(item.get("answer", "")).strip(), ""])
    refs = _safe_refs(data)
    if refs:
        lines.extend(["", "## 参考情報", ""])
        lines.extend(f"- [{item['label']}]({item['url']})" for item in refs)
    lines.extend(["", "## 更新日・著者", "", f"- 更新日: {today}", "- 著者: 羽田野 剛士", ""])
    return "\n".join(lines)


def _build_english(data: dict[str, Any]) -> str:
    description = _fit_description(
        data.get("english_description", ""), 50, 180, "English description"
    )
    tags = [str(tag).strip() for tag in data.get("english_tags", data.get("tags", [])) if str(tag).strip()]
    audiences, industry = _article_taxonomy(data)
    today = date.today().isoformat()
    lines = [
        "---",
        f"title: {base.yaml_string(str(data.get('english_title', '')).strip())}",
        f"description: {base.yaml_string(description)}",
        f"publishedAt: {today}",
        f"updatedAt: {today}",
        f"category: {base.yaml_string(str(data.get('english_category') or data.get('category') or 'Clinic Management'))}",
        "tags:",
        *[f"  - {base.yaml_string(tag)}" for tag in tags],
        'author: "Tsuyoshi Hadano"',
        "draft: false",
        f"cta: {_cta(data)}",
        "audiences:",
        *[f'  - "{audience}"' for audience in audiences],
        'section: "lhub-usecase"',
        f'industry: "{industry}"',
        'series: "lhub-use-cases"',
        'contentType: "practical-guide"',
        "---",
        "",
        str(data.get("english_summary", "")).strip(),
        "",
        str(data.get("english_body_markdown", "")).strip(),
    ]
    refs = _safe_refs(data)
    if refs:
        lines.extend(["", "## References", ""])
        lines.extend(f"- [{item['label']}]({item['url']})" for item in refs)
    lines.append("")
    return "\n".join(lines)


def write_outputs(slug: str, data: dict[str, Any], article: str) -> list[Path]:
    base.ARTICLE_DIR.mkdir(parents=True, exist_ok=True)
    EN_ARTICLE_DIR.mkdir(parents=True, exist_ok=True)
    social_dir = base.SOCIAL_DIR / slug
    social_dir.mkdir(parents=True, exist_ok=True)
    jp = base.ARTICLE_DIR / f"{slug}.md"
    en = EN_ARTICLE_DIR / f"{slug}.md"
    if jp.exists() or en.exists():
        raise FileExistsError(f"Article slug already exists: {slug}")
    jp.write_text(article, encoding="utf-8")
    en.write_text(_build_english(data), encoding="utf-8")
    outputs = [jp, en]
    for filename, key in {"x.md": "social_x", "facebook.md": "social_facebook", "linkedin.md": "social_linkedin"}.items():
        path = social_dir / filename
        path.write_text(str(data.get(key, "")).strip() + "\n", encoding="utf-8")
        outputs.append(path)
    return outputs


# Patch the proven Drive reader/state machine while replacing selection, privacy,
# editorial research and output formatting for the daily publication use case.
base.document_record = document_record
base.is_unprocessed_or_updated = is_unprocessed_or_updated
base.mark_started = mark_started
base.mark_finished = mark_finished
base.select_target_doc = select_target_doc
base.call_openai_once = call_openai_once
base.build_article = build_article
base.write_outputs = write_outputs
base.MAX_SEED_FILES = MAX_SCAN

if __name__ == "__main__":
    try:
        raise SystemExit(base.main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        raise SystemExit(1)
