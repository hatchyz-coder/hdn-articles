#!/usr/bin/env python3
"""Privacy hardening wrapper for the resilient Drive editorial generator."""
from __future__ import annotations

import re

import generate_from_drive_editorial_v2 as impl
from generate_from_drive_editorial_v2 import *  # noqa: F401,F403
from generate_from_drive_editorial_v2 import _state_key, _verify_approved_folder

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
            # If the first pass already replaced the label but left the value, redact
            # the marker plus its immediately following token as well.
            sanitized = re.sub(r"\[REDACTED:credential_secret\]\s+[^\s\n]+", "[REDACTED:credential_secret]", sanitized)
            flags.append("credential_secret")
    return sanitized, sorted(set(flags))


impl.sanitize_seed_text = sanitize_seed_text


def main() -> int:
    return impl.main()


if __name__ == "__main__":
    raise SystemExit(main())
