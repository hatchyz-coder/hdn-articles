#!/usr/bin/env python3
"""Canonical resilient publisher for the approved private LHub/Drive editorial backlog."""
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
MAX_SCAN = 5000
PROCESSOR_VERSION = 4
HARD_MIN_SCORE = 72
EXPECTED_FOLDER_FINGERPRINT = "377cdda8bba3afb0cbf97915b88d8afb46a313417c07b2885cae8c3b76997bc0"

REPROCESS_ON_VERSION_CHANGE = {
    "skipped_confidential", "low_score", "manual_review", "format_error", "api_error",
    "api_timeout", "os_timeout", "processing", "dry_run", "source_error",
}
RETRYABLE = {"processing", "api_timeout", "os_timeout", "dry_run", "format_error", "api_error", "source_error"}
TERMINAL_CONSUMED_STATUSES = {"generated", "published", "published_manual", "duplicate_source"}

KEYWORD_WEIGHTS = {
    "クリニック": 10, "医療": 9, "病院": 8, "歯科": 8, "診療": 9,
    "自由診療": 12, "オンライン診療": 12, "患者": 10, "LINE": 10,
    "LHub": 12, "予約": 7, "問診": 8, "決済": 7, "集患": 7,
    "医療広告": 10, "薬機法": 10, "景表法": 10, "SNS": 7,
    "YouTube": 7, "動画": 6, "経営": 6, "DX": 5, "業務改善": 7, "CRM": 7,
}
OFF_BRAND = {"NFT", "仮想通貨", "暗号資産", "占い", "競馬", "パチンコ", "カジノ", "CBD", "大麻", "VAPE", "電子タバコ", "アダルト", "風俗"}

CREDENTIAL_VALUE_PATTERNS = (
    r"(?i)(パスワード|APIキー|秘密鍵|認証情報|アクセストークン|refresh_token|client_secret)\s*[:：=]\s*[^\s\n]+",
    r"(?i)(authorization\s*:\s*bearer)\s+[^\s\n]+",
)
PRIVATE_LABELED_NAME_PATTERNS = (
    r"(?i)(顧客名|取引先名|会社名|法人名|医院名|クリニック名|店舗名|担当者名|院長名|医師名)\s*[:：=]\s*[^\n、。]{1,80}",
    r"(?i)(client|customer|company|clinic|doctor|contact)\s+name\s*[:=]\s*[^\n,.;]{1,80}",
)
PUBLIC_AUTO_REDACTIONS = (
    (r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", "[contact omitted]"),
    (r"(?:\+81[-\s]?)?0\d{1,4}[-\s]?\d{1,4}[-\s]?\d{3,4}", "[contact omitted]"),
    (r"(?i)(パスワード|APIキー|秘密鍵|認証情報|アクセストークン|refresh_token|client_secret)\s*[:：=]\s*\S+", "[sensitive value omitted]"),
    (r"(患者氏名|患者名|患者ID|カルテ番号|診察券番号)\s*[:：=]\s*\S+", "[patient identifier omitted]"),
    (r"(マイナンバー|個人番号|運転免許証番号|保険証番号)\s*[:：=]?\s*[A-Z0-9０-９-]{4,}", "[personal identifier omitted]"),
)
HARD_PUBLIC_PATTERNS = (
    ("credential_secret", r"(?i)(パスワード|APIキー|秘密鍵|認証情報|アクセストークン|refresh_token|client_secret)\s*[:：=]\s*\S+"),
    ("patient_value", r"(患者氏名|患者名|患者ID|カルテ番号|診察券番号)\s*[:：=]\s*\S+"),
    ("national_id_value", r"(マイナンバー|個人番号|運転免許証番号|保険証番号)\s*[:：=]?\s*[A-Z0-9０-９-]{4,}"),
)
PRIVATE_REFERENCE_URL = re.compile(r"^https?://(?:docs|drive)\.google\.com/", re.I)
PUBLIC_TEXT_KEYS = {
    "title", "description", "summary", "body_markdown", "social_x", "social_facebook",
    "social_linkedin", "english_title", "english_description", "english_summary",
    "english_body_markdown", "category", "english_category",
}
MIN_JP_BODY_CHARS = 1200
MIN_EN_BODY_CHARS = 900


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
    status = str(record.get("status", ""))
    if status in TERMINAL_CONSUMED_STATUSES:
        return False
    version = int(record.get("processorVersion", 0) or 0)
    if status in REPROCESS_ON_VERSION_CHANGE and version < PROCESSOR_VERSION:
        return True
    if record.get("modifiedTime") != doc.get("modifiedTime"):
        return True
    if status in RETRYABLE and int(record.get("retry_count", 0)) <= base.MAX_RETRIES:
        return True
    return False


def mark_started(state: dict[str, Any], doc: dict[str, Any]) -> None:
    record = _record(state, doc["id"])
    old_version = int(record.get("processorVersion", 0) or 0)
    retry = 0 if old_version < PROCESSOR_VERSION else int(record.get("retry_count", 0))
    record.update({
        "modifiedTime": doc.get("modifiedTime"), "status": "processing", "startedAt": base.now_iso(),
        "retry_count": retry, "processorVersion": PROCESSOR_VERSION,
    })
    state["updatedAt"] = base.now_iso()


def mark_finished(state: dict[str, Any], doc: dict[str, Any], status: str, detail: dict[str, Any], permanent: bool) -> None:
    record = _record(state, doc["id"])
    retry = int(record.get("retry_count", 0)) + (0 if permanent else 1)
    safe_detail = {k: v for k, v in detail.items() if k in {"reason", "score", "slug", "manualReview", "sourceProcessing"}}
    record.update({
        "modifiedTime": doc.get("modifiedTime"), "status": status, "finishedAt": base.now_iso(),
        "retry_count": retry, "processorVersion": PROCESSOR_VERSION, **safe_detail,
    })
    state["updatedAt"] = base.now_iso()


def relevance_score(name: str) -> int:
    upper = name.upper()
    if any(term.upper() in upper for term in OFF_BRAND):
        return -100
    return sum(weight for term, weight in KEYWORD_WEIGHTS.items() if term.upper() in upper)


def is_marked_published(name: str) -> bool:
    normalized = str(name).replace("　", " ")
    patterns = (r"(?:^|[\s_\-])済(?:$|[\s_\-])", r"[（(]\s*(?:\d{6})?済\s*[）)]")
    return any(re.search(pattern, normalized) for pattern in patterns)


def queue_sort_key(doc: dict[str, Any]) -> tuple[Any, ...]:
    name = str(doc.get("name", ""))
    match = re.search(r"LH\s*(\d+)\s*_\s*記事\s*(\d+)", name, re.I)
    if match:
        return (0, int(match.group(1)), int(match.group(2)), name)
    return (1, str(doc.get("modifiedTime", "")), name)


def candidate_sort_key(state: dict[str, Any], doc: dict[str, Any]) -> tuple[Any, ...]:
    record = state.get("documents", {}).get(_state_key(doc["id"]), {})
    status = str(record.get("status", ""))
    retry_penalty = 1 if status in RETRYABLE else 0
    return (retry_penalty, *queue_sort_key(doc))


def _verify_approved_folder(folder_id: str) -> None:
    if hashlib.sha256(folder_id.encode("utf-8")).hexdigest() != EXPECTED_FOLDER_FINGERPRINT:
        raise RuntimeError("Configured Drive editorial folder does not match the approved daily queue")


def select_target_doc(drive: Any, state: dict[str, Any], folder_id: str, args: Any, timer: Any):
    with timer.section("driveSeconds", "Drive select editorial seed"):
        _verify_approved_folder(folder_id)
        source_folder = drive.files().get(fileId=folder_id, fields="id,mimeType,parents", supportsAllDrives=True).execute()
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
        candidates = [doc for doc in docs if is_unprocessed_or_updated(state, doc) and not is_marked_published(str(doc.get("name", "")))]
        timer.metrics["newDocuments"] = len(candidates)
        candidates.sort(key=lambda doc: candidate_sort_key(state, doc))
        return (candidates[0], "daily_backlog_queue") if candidates else (None, "daily_backlog_queue")


def sanitize_seed_text(text: str) -> tuple[str, list[str]]:
    sanitized = str(text)
    flags: list[str] = []
    # Remove complete credential label/value pairs before generic sensitive-label redaction,
    # otherwise a broad pattern can erase only the label and leave the secret value behind.
    for pattern in CREDENTIAL_VALUE_PATTERNS:
        if re.search(pattern, sanitized):
            sanitized = re.sub(pattern, "[REDACTED:credential_secret]", sanitized)
            flags.append("credential_secret")
    for label, pattern in base.SENSITIVE_PATTERNS:
        if re.search(pattern, sanitized, flags=re.I):
            sanitized = re.sub(pattern, f"[REDACTED:{label}]", sanitized, flags=re.I)
            flags.append(label)
    drive_pattern = r"https?://(?:docs|drive)\.google\.com/\S+"
    if re.search(drive_pattern, sanitized, flags=re.I):
        sanitized = re.sub(drive_pattern, "[REDACTED:drive_url]", sanitized, flags=re.I)
        flags.append("drive_url")
    for pattern in PRIVATE_LABELED_NAME_PATTERNS:
        if re.search(pattern, sanitized):
            sanitized = re.sub(pattern, "[REDACTED:private_name]", sanitized)
            flags.append("private_name")
    return sanitized, sorted(set(flags))


def _existing_titles() -> list[str]:
    titles: list[str] = []
    pattern = re.compile(r'^title:\s*["\']?(.*?)["\']?\s*$', re.MULTILINE)
    for path in sorted(base.ARTICLE_DIR.glob("*.md")):
        match = pattern.search(path.read_text(encoding="utf-8"))
        if match:
            titles.append(match.group(1))
    return titles[-200:]


def _openai_raw(doc: dict[str, Any], source_text: str, source_processing: dict[str, Any], timer: Any, mock_timeout: bool, feedback: list[str] | None = None) -> dict[str, Any]:
    instructions = PROMPT_PATH.read_text(encoding="utf-8")
    sanitized_text, redactions = sanitize_seed_text(source_text)
    user_input = {
        "today": date.today().isoformat(),
        "seed_title": "Private LHub editorial backlog seed",
        "seed_text": sanitized_text,
        "source_processing": {**source_processing, "preRedactions": redactions},
        "allowed_links": base.ALLOWED_LINKS,
        "existing_article_titles": _existing_titles(),
        "editorial_goal": "Use the sanitized private draft only as a seed. Research current public sources and publish a useful differentiated HDN article whenever possible.",
        "quality_feedback_from_previous_attempt": feedback or [],
    }
    payload_input = json.dumps(user_input, ensure_ascii=False)
    timer.metrics["apiCalls"] = int(timer.metrics.get("apiCalls", 0)) + 1
    timer.metrics["aiEvaluations"] = int(timer.metrics.get("aiEvaluations", 0)) + 1
    timer.metrics["inputCharacters"] = int(timer.metrics.get("inputCharacters", 0)) + len(payload_input) + len(instructions)
    if mock_timeout:
        raise TimeoutError("OpenAI mock timed out")
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    with timer.section("openaiSeconds", "OpenAI editorial generation with web research"):
        try:
            response = requests.post(
                "https://api.openai.com/v1/responses", timeout=(10, 120),
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": os.getenv("OPENAI_MODEL", "gpt-5-mini"), "instructions": instructions, "input": payload_input, "tools": [{"type": "web_search", "search_context_size": "medium"}], "max_output_tokens": 14000, "store": False},
            )
        except requests.Timeout as exc:
            raise TimeoutError("OpenAI API timed out during editorial generation") from exc
    response.raise_for_status()
    payload = response.json()
    output_text = payload.get("output_text", "")
    if not output_text:
        chunks: list[str] = []
        for item in payload.get("output", []):
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    chunks.append(content.get("text", ""))
        output_text = "\n".join(chunks)
    output_text = re.sub(r"^```(?:json)?\s*|\s*```$", "", str(output_text).strip(), flags=re.I | re.S)
    if not output_text:
        raise ValueError("OpenAI response did not contain JSON output")
    return json.loads(output_text)


def _depth_issues(data: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    for key in ("title", "summary", "body_markdown", "english_title", "english_summary", "english_body_markdown"):
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


def call_openai_once(doc: dict[str, Any], source_text: str, source_processing: dict[str, Any], timer: Any, mock_timeout: bool) -> dict[str, Any]:
    first = _openai_raw(doc, source_text, source_processing, timer, mock_timeout)
    feedback = _depth_issues(first)
    if first.get("should_generate") and int(first.get("score", 0) or 0) < HARD_MIN_SCORE:
        feedback.append("editorial_score_below_72_after_first_pass")
    if not first.get("should_generate") or not feedback:
        return first
    second = _openai_raw(doc, source_text, source_processing, timer, mock_timeout, feedback)
    remaining = _depth_issues(second)
    if remaining and second.get("should_generate"):
        second["should_generate"] = False
        second["score"] = min(int(second.get("score", 0) or 0), HARD_MIN_SCORE - 1)
        second["skip_reason"] = "Final JP/EN pair remained objectively too thin after automatic rewrite: " + ", ".join(remaining)
    return second


def _clean_public_text(value: str) -> str:
    result = value
    for pattern, replacement in PUBLIC_AUTO_REDACTIONS:
        result = re.sub(pattern, replacement, result, flags=re.I)
    return result


def sanitize_public_output(data: dict[str, Any]) -> list[str]:
    changed: list[str] = []
    for key in PUBLIC_TEXT_KEYS:
        if isinstance(data.get(key), str):
            cleaned = _clean_public_text(data[key])
            if cleaned != data[key]:
                changed.append(key)
            data[key] = cleaned
    for key in ("tags", "english_tags"):
        if isinstance(data.get(key), list):
            data[key] = [_clean_public_text(str(value)) for value in data[key] if str(value).strip()]
    for item in data.get("faq", []):
        if isinstance(item, dict):
            for key in ("question", "answer"):
                if isinstance(item.get(key), str):
                    item[key] = _clean_public_text(item[key])
    safe_refs: list[dict[str, str]] = []
    for item in data.get("references", []):
        if not isinstance(item, dict):
            continue
        label = _clean_public_text(str(item.get("label", "")).strip())
        url = str(item.get("url", "")).strip()
        if PRIVATE_REFERENCE_URL.match(url):
            changed.append("private_reference")
            continue
        if label and re.match(r"^https?://", url):
            safe_refs.append({"label": label, "url": url})
    data["references"] = safe_refs
    return sorted(set(changed))


def _published_payload(data: dict[str, Any]) -> str:
    parts = [str(data.get(key, "")) for key in PUBLIC_TEXT_KEYS]
    parts.extend(str(tag) for tag in data.get("tags", []))
    parts.extend(str(tag) for tag in data.get("english_tags", []))
    for item in data.get("faq", []):
        if isinstance(item, dict):
            parts.extend([str(item.get("question", "")), str(item.get("answer", ""))])
    for item in data.get("references", []):
        if isinstance(item, dict):
            parts.extend([str(item.get("label", "")), str(item.get("url", ""))])
    return "\n".join(parts)


def validate_sanitized_output(data: dict[str, Any]) -> list[str]:
    sanitize_public_output(data)
    payload = _published_payload(data)
    return [label for label, pattern in HARD_PUBLIC_PATTERNS if re.search(pattern, payload, flags=re.I)]


def _description(value: Any, fallback: Any, max_chars: int) -> str:
    text = str(value or "").strip() or str(fallback or "").strip()
    min_chars = 60 if max_chars == 160 else 50
    if len(text) < min_chars:
        fallback_text = str(fallback or "").strip()
        if fallback_text and fallback_text not in text:
            text = f"{text} {fallback_text}".strip()
    if len(text) < min_chars:
        suffix = "実務で確認したい論点、判断基準、運用上の注意点、失敗を避けるための確認ポイントまで具体的に整理します。" if max_chars == 160 else "Practical implications, trade-offs, implementation checks, and operational decision points are explained for operators."
        text = f"{text} {suffix}".strip()
    while len(text) < min_chars:
        extra = "現場で使える判断材料を補足します。" if max_chars == 160 else "Additional practical guidance is included."
        text = f"{text} {extra}".strip()
    if len(text) > max_chars:
        text = text[: max_chars - 1].rstrip() + "…"
    return text


def _safe_refs(data: dict[str, Any]) -> list[dict[str, str]]:
    return [item for item in data.get("references", [])[:12] if isinstance(item, dict) and item.get("label") and re.match(r"^https?://", str(item.get("url", "")))]


def _cta(data: dict[str, Any]) -> str:
    value = str(data.get("cta", "consultation")).strip()
    return value if value in {"consultation", "lhub", "self-pay", "sns"} else "consultation"


def build_article(data: dict[str, Any], doc: dict[str, Any]) -> str:
    title = str(data.get("title", "")).strip()
    description = _description(data.get("description"), data.get("summary") or title, 160)
    tags = [str(tag).strip() for tag in data.get("tags", []) if str(tag).strip()]
    today = date.today().isoformat()
    lines = ["---", f"title: {base.yaml_string(title)}", f"description: {base.yaml_string(description)}", f"publishedAt: {today}", f"updatedAt: {today}", f"category: {base.yaml_string(str(data.get('category') or 'クリニック経営'))}", "tags:", *[f"  - {base.yaml_string(tag)}" for tag in tags], 'author: "羽田野 剛士"', "draft: false", "featured: false", f"cta: {_cta(data)}", "---", "", str(data.get("summary", "")).strip(), "", str(data.get("body_markdown", "")).strip()]
    faq = data.get("faq", [])[:5]
    if faq:
        lines.extend(["", "## よくある質問", ""])
        for item in faq:
            lines.extend([f"### {str(item.get('question', '')).strip()}", "", str(item.get("answer", "")).strip(), ""])
    refs = _safe_refs(data)
    if refs:
        lines.extend(["", "## 参考情報", "", *[f"- [{item['label']}]({item['url']})" for item in refs]])
    lines.extend(["", "## 更新日・著者", "", f"- 更新日: {today}", "- 著者: 羽田野 剛士", ""])
    return "\n".join(lines)


def _build_english(data: dict[str, Any]) -> str:
    title = str(data.get("english_title", "")).strip()
    description = _description(data.get("english_description"), data.get("english_summary") or title, 180)
    tags = [str(tag).strip() for tag in data.get("english_tags", data.get("tags", [])) if str(tag).strip()]
    today = date.today().isoformat()
    lines = ["---", f"title: {base.yaml_string(title)}", f"description: {base.yaml_string(description)}", f"publishedAt: {today}", f"updatedAt: {today}", f"category: {base.yaml_string(str(data.get('english_category') or data.get('category') or 'Clinic Management'))}", "tags:", *[f"  - {base.yaml_string(tag)}" for tag in tags], 'author: "Tsuyoshi Hadano"', "draft: false", f"cta: {_cta(data)}", "---", "", str(data.get("english_summary", "")).strip(), "", str(data.get("english_body_markdown", "")).strip()]
    refs = _safe_refs(data)
    if refs:
        lines.extend(["", "## References", "", *[f"- [{item['label']}]({item['url']})" for item in refs]])
    lines.append("")
    return "\n".join(lines)


def unique_slug(suggested: str, doc_id: str) -> str:
    base_slug = base.normalize_slug(suggested, doc_id)
    suffix = hashlib.sha256(doc_id.encode("utf-8")).hexdigest()[:8]
    candidates = [base_slug, f"{base_slug}-{suffix}"]
    candidates.extend(f"{base_slug}-{suffix}-{index}" for index in range(2, 1000))
    for slug in candidates:
        if not (base.ARTICLE_DIR / f"{slug}.md").exists() and not (EN_ARTICLE_DIR / f"{slug}.md").exists():
            return slug
    raise RuntimeError("Could not allocate a unique article slug without overwriting existing content")


def write_outputs(slug: str, data: dict[str, Any], article: str) -> list[Path]:
    base.ARTICLE_DIR.mkdir(parents=True, exist_ok=True)
    EN_ARTICLE_DIR.mkdir(parents=True, exist_ok=True)
    social_dir = base.SOCIAL_DIR / slug
    social_dir.mkdir(parents=True, exist_ok=True)
    jp = base.ARTICLE_DIR / f"{slug}.md"
    en = EN_ARTICLE_DIR / f"{slug}.md"
    if jp.exists() or en.exists():
        raise FileExistsError(f"Refusing to overwrite existing article pair: {slug}")
    jp.write_text(article, encoding="utf-8")
    en.write_text(_build_english(data), encoding="utf-8")
    outputs = [jp, en]
    for filename, key in {"x.md": "social_x", "facebook.md": "social_facebook", "linkedin.md": "social_linkedin"}.items():
        path = social_dir / filename
        path.write_text(str(data.get(key, "")).strip() + "\n", encoding="utf-8")
        outputs.append(path)
    return outputs


def main() -> int:
    args = base.parse_args()
    args.min_score = max(HARD_MIN_SCORE, int(args.min_score))
    timer = base.RunTimer()
    state = base.load_json(args.state_path, {"documents": {}})
    report: dict[str, Any] = {"selected": False, "runLog": [], "createdAt": base.now_iso(), "processorVersion": PROCESSOR_VERSION}
    if not args.folder_id:
        raise RuntimeError("DRIVE_EDITORIAL_FOLDER_ID is required")
    with timer.section("driveSeconds", "Google API client setup"):
        drive, docs = base.google_services(args.service_account_json)
    doc, mode = select_target_doc(drive, state, args.folder_id, args, timer)
    report["selectionMode"] = mode
    if not doc:
        return base.finish(args, state, report, timer, False, "no_candidate")

    doc_key = _state_key(doc["id"])
    timer.metrics["selectedDocumentKey"] = doc_key
    report.update({"sourceKey": doc_key, "modifiedTime": doc.get("modifiedTime")})
    doc_url = doc.get("webViewLink") or f"https://docs.google.com/document/d/{doc['id']}"
    record = document_record(state, doc["id"])
    if doc_url in base.existing_source_urls() or doc["id"] in base.excluded_tokens(args.exclude_file) or doc_url in base.excluded_tokens(args.exclude_file):
        mark_finished(state, doc, "duplicate_source", {"reason": "source already consumed"}, permanent=True)
        return base.finish(args, state, report, timer, False, "duplicate_source")
    if int(record.get("processorVersion", 0) or 0) >= PROCESSOR_VERSION and base.retry_count(record) > base.MAX_RETRIES:
        mark_finished(state, doc, "manual_review", {"reason": "retry_count exceeded", "manualReview": True}, permanent=True)
        return base.finish(args, state, report, timer, False, "manual_review_retry_limit")

    mark_started(state, doc)
    base.save_state_and_report(args, state, {**report, "reason": "processing_started"}, timer)
    try:
        with timer.section("docsFetchSeconds", "Google Docs body fetch"):
            text = base.extract_text_from_doc(docs, doc["id"])
        source_text, source_processing = base.select_input_text(text)
    except Exception as exc:
        mark_finished(state, doc, "source_error", {"reason": type(exc).__name__}, permanent=False)
        return base.finish(args, state, report, timer, False, "source_error")

    sanitized_seed, pre_redactions = sanitize_seed_text(source_text)
    report["sourceProcessing"] = {**source_processing, "preRedactionCount": len(pre_redactions)}
    if args.dry_run:
        mark_finished(state, doc, "dry_run", {"reason": "dry_run completed", "sourceProcessing": source_processing}, permanent=False)
        return base.finish(args, state, report, timer, False, "dry_run")
    try:
        data = call_openai_once(doc, sanitized_seed, source_processing, timer, args.mock_openai_timeout)
    except TimeoutError as exc:
        mark_finished(state, doc, "api_timeout", {"reason": str(exc), "sourceProcessing": source_processing}, permanent=False)
        return base.finish(args, state, report, timer, False, "api_timeout")
    except Exception as exc:
        mark_finished(state, doc, "api_error", {"reason": type(exc).__name__, "sourceProcessing": source_processing}, permanent=False)
        return base.finish(args, state, report, timer, False, "api_error")

    score = int(data.get("score", 0) or 0)
    if not data.get("should_generate") or score < args.min_score:
        mark_finished(state, doc, "low_score", {"reason": data.get("skip_reason", "low score"), "score": score}, permanent=True)
        return base.finish(args, state, {**report, "score": score}, timer, False, "low_score")
    residual_flags = validate_sanitized_output(data)
    if residual_flags:
        mark_finished(state, doc, "skipped_confidential", {"reason": "high-risk sensitive material remained after deterministic public-output sanitization", "score": score}, permanent=True)
        return base.finish(args, state, {**report, "score": score, "residualFlagCount": len(residual_flags)}, timer, False, "confidential_output")

    slug = unique_slug(str(data.get("suggested_slug", "")), doc["id"])
    try:
        outputs = write_outputs(slug, data, build_article(data, doc))
    except Exception as exc:
        mark_finished(state, doc, "format_error", {"reason": type(exc).__name__, "score": score}, permanent=False)
        return base.finish(args, state, {**report, "score": score}, timer, False, "format_error")

    research_review = {"additionalVerificationTopics": data.get("additional_verification_topics", []), "officialSourceCandidates": data.get("official_source_candidates", []), "unsupportedClaimsFromSourceOnly": data.get("unsupported_claims_from_source_only", [])}
    mark_finished(state, doc, "generated", {"slug": slug, "score": score, "sourceProcessing": source_processing}, permanent=True)
    timer.metrics["articlesGenerated"] = 1
    report.update({"selected": True, "slug": slug, "score": score, "eeat": data.get("eeat", {}), "researchReview": research_review, "outputs": [str(path.relative_to(ROOT)) for path in outputs], "preRedactionCount": len(pre_redactions), "aiSanitizationNoteCount": len([x for x in data.get("confidentiality_flags", []) if str(x).strip()])})
    base.write_output("slug", slug)
    base.write_output("score", str(score))
    base.write_output("eeat", json.dumps(data.get("eeat", {}), ensure_ascii=False))
    base.write_output("research_review", json.dumps(research_review, ensure_ascii=False))
    return base.finish(args, state, report, timer, True, "generated")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}", file=sys.stderr, flush=True)
        raise SystemExit(1)
