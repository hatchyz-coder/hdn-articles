#!/usr/bin/env python3
"""Cost-optimized wrapper for official-source article generation."""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

import requests

import generate_content as content

MODEL_PRICING_USD_PER_M = {
    "gpt-5-mini": {"input": 0.25, "cached_input": 0.025, "output": 2.00},
    "gpt-5.6-luna": {"input": 0.20, "cached_input": 0.02, "output": 1.20},
}
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def _record_usage(payload: dict[str, Any], model: str) -> None:
    usage = payload.get("usage") or {}
    input_tokens = int(usage.get("input_tokens") or 0)
    output_tokens = int(usage.get("output_tokens") or 0)
    details = usage.get("input_tokens_details") or {}
    cached_tokens = int(details.get("cached_tokens") or 0)

    estimated: float | None = None
    pricing = MODEL_PRICING_USD_PER_M.get(model)
    if pricing:
        uncached = max(0, input_tokens - cached_tokens)
        estimated = (
            uncached * pricing["input"] / 1_000_000
            + cached_tokens * pricing["cached_input"] / 1_000_000
            + output_tokens * pricing["output"] / 1_000_000
        )

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        lines = [
            "## OpenAI official-source usage",
            "",
            f"- Model: {model}",
            f"- Input tokens: {input_tokens}",
            f"- Cached input tokens: {cached_tokens}",
            f"- Output tokens: {output_tokens}",
            "- Paid OpenAI web-search calls: 0",
        ]
        if estimated is not None:
            lines.append(f"- Estimated API cost for this generation: ${estimated:.4f}")
        lines.append("")
        with Path(summary_path).open("a", encoding="utf-8") as handle:
            handle.write("\n".join(lines))


def call_openai_cost_optimized(
    source_url: str,
    source_title: str,
    source_text: str,
    category: str,
    cta: str,
    reference_context: dict[str, Any],
) -> dict[str, Any]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured in GitHub Actions secrets")

    model = os.environ.get("OPENAI_MODEL", "gpt-5-mini")
    instructions = content.PROMPT_PATH.read_text(encoding="utf-8")
    user_input = {
        "source_url": source_url,
        "source_title": source_title,
        "source_text": source_text,
        "requested_category": category,
        "cta_type": cta,
        "allowed_links": content.ALLOWED_LINKS,
        "private_editorial_reference": {
            "internal_operations": reference_context.get("internal_operations", []),
            "lhub_archive": reference_context.get("lhub_archive", []),
        },
    }

    max_attempts = max(1, min(int(os.getenv("OPENAI_MAX_ATTEMPTS", "2")), 2))
    read_timeout = max(90, min(int(os.getenv("OPENAI_READ_TIMEOUT_SECONDS", "180")), 240))
    max_output_tokens = max(7000, min(int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "9000")), 10000))
    request_json = {
        "model": model,
        "instructions": instructions,
        "input": json.dumps(user_input, ensure_ascii=False),
        "reasoning": {"effort": "low"},
        "max_output_tokens": max_output_tokens,
        "prompt_cache_key": "hdn-official-source-v2",
        "store": False,
    }

    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.post(
                "https://api.openai.com/v1/responses",
                timeout=(10, read_timeout),
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=request_json,
            )
        except requests.Timeout as exc:
            if attempt < max_attempts:
                time.sleep(12)
                continue
            raise TimeoutError("OpenAI API timed out during official-source generation") from exc

        if response.status_code in RETRYABLE_STATUS and attempt < max_attempts:
            time.sleep(12)
            continue

        response.raise_for_status()
        payload = response.json()
        _record_usage(payload, model)

        output_text = payload.get("output_text")
        if not output_text:
            pieces: list[str] = []
            for item in payload.get("output", []):
                if item.get("type") != "message":
                    continue
                for part in item.get("content", []):
                    if part.get("type") == "output_text" and part.get("text"):
                        pieces.append(part["text"])
            output_text = "\n".join(pieces)

        if not output_text:
            raise RuntimeError("OpenAI response did not contain output text")
        output_text = re.sub(r"^```(?:json)?\s*|\s*```$", "", output_text.strip(), flags=re.I | re.S)
        return json.loads(output_text)

    raise RuntimeError("OpenAI official-source generation failed without a response")


content.call_openai = call_openai_cost_optimized

if __name__ == "__main__":
    try:
        raise SystemExit(content.main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
