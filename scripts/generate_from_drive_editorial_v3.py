#!/usr/bin/env python3
"""Privacy, retry, deduplication and backlog hardening for the Drive editorial generator."""
from __future__ import annotations

import hashlib
import re
from typing import Any

import generate_from_drive_editorial_v2 as impl
from generate_from_drive_editorial_v2 import *  # noqa: F401,F403
from generate_from_drive_editorial_v2 import _state_key, _verify_approved_folder

impl.PROCESSOR_VERSION = 3
PROCESSOR_VERSION = impl.PROCESSOR_VERSION

HARD_MIN_SCORE = 72
_base_parse_args = impl.base.parse_args


def _parse_args_with_floor():
    args = _base_parse_args()
    args.min_score = max(HARD_MIN_SCORE, int(args.min_score))
    return args


impl.base.parse_args = _parse_args_with_floor

impl.MAX_SCAN = 5000
impl.base.MAX_FOLDER_SCAN = 1000
MAX_SCAN = impl.MAX_SCAN

impl.REPROCESS_ON_VERSION_CHANGE = set(impl.REPROCESS_ON_VERSION_CHANGE) | {
    "api_timeout",
    "os_timeout",
    "processing",
    "dry_run",
}
REPROCESS_ON_VERSION_CHANGE = impl.REPROCESS_ON_VERSION_CHANGE

TERMINAL_CONSUMED_STATUSES = {"generated", "published", "published_manual", "duplicate_source"}
_v2_is_unprocessed_or_updated = impl.is_unprocessed_or_updated


def is_unprocessed_or_updated(state: dict[str, Any], doc: dict[str, Any]) -> bool:
    record = state.get("documents", {}).get(_state_key(doc["id"]))
    if record and str(record.get("status", "")) in TERMINAL_CONSUMED_STATUSES:
        return False
    return _v2_is_unprocessed_or_updated(state, doc)


impl.is_unprocessed_or_updated = is_unprocessed_or_updated

_v2_sanitize_seed_text = impl.sanitize_seed_text

CREDENTIAL_VALUE_PATTERNS = (
    r"(?i)(パスワード|APIキー|秘密鍵|認証情報|アクセストークン|refresh_token|client_secret)\s*[:：=]\s*[^\s\n]+",
    r"(?i)(authorization\s*:\s*bearer)\s+[^\s\n]+",
)
PRIVATE_LABELED_NAME_PATTERNS = (
    r"(?i)(顧客名|取引先名|会社名|法人名|医院名|クリニック名|店舗名|担当者名|院長名|医師名)\s*[:：=]\s*[^\n、。]{1,80}",
    r"(?i)(client|customer|company|clinic|doctor|contact)\s+name\s*[:=]\s*[^\n,.;]{1,80}",
)


def sanitize_seed_text(text: str) -> tuple[str, list[str]]:
    sanitized, flags = _v2_sanitize_seed_text(text)
    original = str(text)
    for pattern in CREDENTIAL_VALUE_PATTERNS:
        if re.search(pattern, original):
            sanitized = re.sub(pattern, "[REDACTED:credential_secret]", sanitized)
            sanitized = re.sub(r"\[REDACTED:credential_secret\]\s+[^\s\n]+", "[REDACTED:credential_secret]", sanitized)
            flags.append("credential_secret")
    for pattern in PRIVATE_LABELED_NAME_PATTERNS:
        if re.search(pattern, sanitized):
            sanitized = re.sub(pattern, "[REDACTED:private_name]", sanitized)
            flags.append("private_name")
    return sanitized, sorted(set(flags))


impl.sanitize_seed_text = sanitize_seed_text

PUBLIC_AUTO_REDACTIONS = (
    (r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", "[contact omitted]"),
    (r"(?:\+81[-\s]?)?0\d{1,4}[-\s]?\d{1,4}[-\s]?\d{3,4}", "[contact omitted]"),
    (r"(?i)(パスワード|APIキー|秘密鍵|認証情報|アクセストークン|refresh_token|client_secret)\s*[:：=]\s*\S+", "[sensitive value omitted]"),
    (r"(患者氏名|患者名|患者ID|カルテ番号|診察券番号)\s*[:：=]\s*\S+", "[patient identifier omitted]"),
    (r"(マイナンバー|個人番号|運転免許証番号|保険証番号)\s*[:：=]?\s*[A-Z0-9０-９-]{4,}", "[personal identifier omitted]"),
)
PRIVATE_REFERENCE_URL = re.compile(r"^https?://(?:docs|drive)\.google\.com/", re.I)
PUBLIC_TEXT_KEYS = {
    "title", "description", "summary", "body_markdown", "social_x", "social_facebook",
    "social_linkedin", "english_title", "english_description", "english_summary",
    "english_body_markdown", "category", "english_category",
}


def sanitize_public_output(data: dict[str, Any]) -> list[str]:
    changed: list[str] = []

    def clean(value: str) -> str:
        result = value
        for pattern, replacement in PUBLIC_AUTO_REDACTIONS:
            next_value = re.sub(pattern, replacement, result, flags=re.I)
            if next_value != result:
                changed.append(replacement)
            result = next_value
        return result

    for key in PUBLIC_TEXT_KEYS:
        if key in data and isinstance(data[key], str):
            data[key] = clean(data[key])

    for key in ("tags", "english_tags"):
        if isinstance(data.get(key), list):
            data[key] = [clean(str(value)) for value in data[key] if str(value).strip()]

    for item in data.get("faq", []):
        if isinstance(item, dict):
            for key in ("question", "answer"):
                if isinstance(item.get(key), str):
                    item[key] = clean(item[key])

    safe_references: list[dict[str, Any]] = []
    for item in data.get("references", []):
        if not isinstance(item, dict):
            continue
        label = clean(str(item.get("label", "")))
        url = str(item.get("url", "")).strip()
        if PRIVATE_REFERENCE_URL.match(url):
            changed.append("private_reference_removed")
            continue
        safe_references.append({**item, "label": label, "url": url})
    data["references"] = safe_references
    return changed


def validate_sanitized_output(data: dict[str, Any]) -> list[str]:
    sanitize_public_output(data)
    payload = impl._published_payload(data)
    extra_parts = [
        str(data.get("category", "")),
        str(data.get("english_category", "")),
        " ".join(str(tag) for tag in data.get("tags", [])),
        " ".join(str(tag) for tag in data.get("english_tags", [])),
    ]
    for item in data.get("references", []):
        if isinstance(item, dict):
            extra_parts.extend([str(item.get("label", "")), str(item.get("url", ""))])
    payload = payload + "\n" + "\n".join(extra_parts)
    hard_patterns = [
        (label, pattern)
        for label, pattern in impl.PUBLIC_SENSITIVE_PATTERNS
        if label in {"credential_secret", "patient_value", "national_id_value"}
    ]
    return [label for label, pattern in hard_patterns if re.search(pattern, payload, flags=re.I)]


impl.validate_sanitized_output = validate_sanitized_output


def unique_slug(suggested: str, doc_id: str) -> str:
    base_slug = impl.base.normalize_slug(suggested, doc_id)
    suffix = hashlib.sha256(doc_id.encode("utf-8")).hexdigest()[:8]
    candidates = [base_slug, f"{base_slug}-{suffix}"]
    candidates.extend(f"{base_slug}-{suffix}-{index}" for index in range(2, 1000))
    for slug in candidates:
        if not (impl.base.ARTICLE_DIR / f"{slug}.md").exists() and not (impl.EN_ARTICLE_DIR / f"{slug}.md").exists():
            return slug
    raise RuntimeError("Could not allocate a unique article slug without overwriting existing content")


impl.unique_slug = unique_slug

_v2_write_outputs = impl.write_outputs


def write_outputs(slug: str, data: dict[str, Any], article: str):
    jp = impl.base.ARTICLE_DIR / f"{slug}.md"
    en = impl.EN_ARTICLE_DIR / f"{slug}.md"
    if jp.exists() or en.exists():
        raise FileExistsError(f"Refusing to overwrite existing published article pair: {slug}")
    return _v2_write_outputs(slug, data, article)


impl.write_outputs = write_outputs


def main() -> int:
    return impl.main()


if __name__ == "__main__":
    raise SystemExit(main())
