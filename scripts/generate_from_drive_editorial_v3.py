#!/usr/bin/env python3
"""Privacy and retry hardening wrapper for the resilient Drive editorial generator."""
from __future__ import annotations

import re
from typing import Any

import generate_from_drive_editorial_v2 as impl
from generate_from_drive_editorial_v2 import *  # noqa: F401,F403
from generate_from_drive_editorial_v2 import _state_key, _verify_approved_folder

# Legacy runs permanently exhausted some transient states before the resilient processor
# existed. On a processor-version upgrade, allow exactly one fresh retry cycle for them.
impl.REPROCESS_ON_VERSION_CHANGE = set(impl.REPROCESS_ON_VERSION_CHANGE) | {
    "api_timeout",
    "os_timeout",
    "processing",
    "dry_run",
}
REPROCESS_ON_VERSION_CHANGE = impl.REPROCESS_ON_VERSION_CHANGE

_v2_sanitize_seed_text = impl.sanitize_seed_text

CREDENTIAL_VALUE_PATTERNS = (
    r"(?i)(パスワード|APIキー|秘密鍵|認証情報|アクセストークン|refresh_token|client_secret)\s*[:：=]\s*[^\s\n]+",
    r"(?i)(authorization\s*:\s*bearer)\s+[^\s\n]+",
)


def sanitize_seed_text(text: str) -> tuple[str, list[str]]:
    sanitized, flags = _v2_sanitize_seed_text(text)
    # The legacy pattern can match only the credential label. Perform a second pass
    # that consumes the value too, so no token survives into the model input.
    original = str(text)
    for pattern in CREDENTIAL_VALUE_PATTERNS:
        if re.search(pattern, original):
            sanitized = re.sub(pattern, "[REDACTED:credential_secret]", sanitized)
            sanitized = re.sub(r"\[REDACTED:credential_secret\]\s+[^\s\n]+", "[REDACTED:credential_secret]", sanitized)
            flags.append("credential_secret")
    return sanitized, sorted(set(flags))


impl.sanitize_seed_text = sanitize_seed_text

# Public-output checks should prevent disclosure, not discard an otherwise useful article
# because the model happened to include a contact address or a sensitive-value-shaped token.
# Recoverable findings are removed before the hard residual gate. Only high-risk material
# that survives this deterministic pass can veto publication.
PUBLIC_AUTO_REDACTIONS = (
    (r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", "[contact omitted]"),
    (r"(?:\+81[-\s]?)?0\d{1,4}[-\s]?\d{1,4}[-\s]?\d{3,4}", "[contact omitted]"),
    (r"(?i)(パスワード|APIキー|秘密鍵|認証情報|アクセストークン|refresh_token|client_secret)\s*[:：=]\s*\S+", "[sensitive value omitted]"),
    (r"(患者氏名|患者名|患者ID|カルテ番号|診察券番号)\s*[:：=]\s*\S+", "[patient identifier omitted]"),
    (r"(マイナンバー|個人番号|運転免許証番号|保険証番号)\s*[:：=]?\s*[A-Z0-9０-９-]{4,}", "[personal identifier omitted]"),
)
PUBLIC_TEXT_KEYS = {
    "title", "description", "summary", "body_markdown", "social_x", "social_facebook",
    "social_linkedin", "english_title", "english_description", "english_summary",
    "english_body_markdown",
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
    for item in data.get("faq", []):
        if isinstance(item, dict):
            for key in ("question", "answer"):
                if isinstance(item.get(key), str):
                    item[key] = clean(item[key])
    return changed


def validate_sanitized_output(data: dict[str, Any]) -> list[str]:
    sanitize_public_output(data)
    payload = impl._published_payload(data)
    hard_patterns = [
        (label, pattern)
        for label, pattern in impl.PUBLIC_SENSITIVE_PATTERNS
        if label in {"credential_secret", "patient_value", "national_id_value"}
    ]
    return [label for label, pattern in hard_patterns if re.search(pattern, payload, flags=re.I)]


impl.validate_sanitized_output = validate_sanitized_output


def main() -> int:
    return impl.main()


if __name__ == "__main__":
    raise SystemExit(main())
