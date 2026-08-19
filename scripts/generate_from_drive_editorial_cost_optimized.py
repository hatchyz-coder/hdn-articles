#!/usr/bin/env python3
"""Cost-optimized runner for the HDN Daily Drive editorial publisher.

Keeps the existing editorial selection, privacy, output and quality gates while making
OpenAI usage bounded and observable. This module intentionally does not lower the
editorial score threshold.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import date
from typing import Any

import requests

import generate_from_drive_editorial as editorial
import generate_from_drive_knowledge as base


MODEL_PRICING_USD_PER_M = {
    "gpt-5-mini": {"input": 0.25, "cached_input": 0.025, "output": 2.00},
    "gpt-5.6-luna": {"input": 0.20, "cached_input": 0.02, "output": 1.20},
}
WEB_SEARCH_USD_PER_CALL = 0.01
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def _record_usage(payload: dict[str, Any], timer: Any, model: str) -> None:
    usage = payload.get("usage") or {}
    input_tokens = int(usage.get("input_tokens") or 0)
    output_tokens = int(usage.get("output_tokens") or 0)
    details = usage.get("input_tokens_details") or {}
    cached_tokens = int(details.get("cached_tokens") or 0)
    web_search_calls = sum(
        1 for item in payload.get("output", [])
        if str(item.get("type", "")).startswith("web_search")
    )

    timer.metrics["apiInputTokens"] = input_tokens
    timer.metrics["apiCachedInputTokens"] = cached_tokens
    timer.metrics["apiOutputTokens"] = output_tokens
    timer.metrics["webSearchCalls"] = web_search_calls

    pricing = MODEL_PRICING_USD_PER_M.get(model)
    if pricing:
        uncached = max(0, input_tokens - cached_tokens)
        estimated = (
            uncached * pricing["input"] / 1_000_000
            + cached_tokens * pricing["cached_input"] / 1_000_000
            + output_tokens * pricing["output"] / 1_000_000
            + web_search_calls * WEB_SEARCH_USD_PER_CALL
        )
        timer.metrics["estimatedOpenAiCostUsd"] = round(estimated, 6)


def call_openai_cost_optimized(
    doc: dict[str, Any],
    source_text: str,
    source_processing: dict[str, Any],
    timer: Any,
    mock_timeout: bool,
) -> dict[str, Any]:
    instructions = editorial.PROMPT_PATH.read_text(encoding="utf-8")
    user_input = {
        "today": date.today().isoformat(),
        "seed_title": doc.get("name"),
        "seed_text": source_text,
        "source_processing": source_processing,
        "allowed_links": base.ALLOWED_LINKS,
        "existing_article_titles": editorial._existing_titles(),
        "editorial_goal": (
            "Use the private draft only as a seed. Research current public news/trends "
            "and rebuild the article for HDN's current audience. Use web research only "
            "where it materially supports current or safety-sensitive claims."
        ),
    }
    payload_input = json.dumps(user_input, ensure_ascii=False)
    timer.metrics["aiEvaluations"] = 1
    timer.metrics["inputCharacters"] = len(payload_input) + len(instructions)

    if mock_timeout:
        raise TimeoutError("OpenAI mock timed out")

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    model = os.getenv("OPENAI_MODEL", "gpt-5-mini")
    max_attempts = max(1, min(int(os.getenv("OPENAI_MAX_ATTEMPTS", "2")), 2))
    read_timeout = max(90, min(int(os.getenv("OPENAI_READ_TIMEOUT_SECONDS", "180")), 240))
    max_output_tokens = max(7000, min(int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "9000")), 10000))

    request_json = {
        "model": model,
        "instructions": instructions,
        "input": payload_input,
        "tools": [{"type": "web_search", "search_context_size": "low"}],
        "max_tool_calls": 2,
        "reasoning": {"effort": "low"},
        "max_output_tokens": max_output_tokens,
        "prompt_cache_key": "hdn-drive-editorial-v3",
        "store": False,
    }

    last_error: Exception | None = None
    with timer.section("openaiSeconds", "OpenAI editorial generation with bounded web research"):
        for attempt in range(1, max_attempts + 1):
            timer.metrics["apiCalls"] = attempt
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
                last_error = exc
                if attempt < max_attempts:
                    time.sleep(12)
                    continue
                raise TimeoutError("OpenAI API timed out during editorial generation") from exc

            if response.status_code in RETRYABLE_STATUS and attempt < max_attempts:
                last_error = requests.HTTPError(
                    f"Retryable OpenAI HTTP {response.status_code}", response=response
                )
                time.sleep(12)
                continue

            response.raise_for_status()
            payload = response.json()
            _record_usage(payload, timer, model)

            output_text = payload.get("output_text", "")
            if not output_text:
                chunks: list[str] = []
                for item in payload.get("output", []):
                    for content in item.get("content", []):
                        if content.get("type") == "output_text":
                            chunks.append(content.get("text", ""))
                output_text = "\n".join(chunks)

            output_text = re.sub(
                r"^```(?:json)?\s*|\s*```$", "", output_text.strip(), flags=re.I | re.S
            )
            return json.loads(output_text)

    if last_error:
        raise last_error
    raise RuntimeError("OpenAI editorial generation failed without a response")


# Importing the existing editorial module installs all other proven overrides on base.
# Replace only its OpenAI call with the bounded, observable implementation above.
editorial.call_openai_once = call_openai_cost_optimized
base.call_openai_once = call_openai_cost_optimized


if __name__ == "__main__":
    try:
        raise SystemExit(base.main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        raise SystemExit(1)
