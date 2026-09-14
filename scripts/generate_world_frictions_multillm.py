#!/usr/bin/env python3
"""Provider-resilient World Frictions runner.

Primary path: Gemini free-tier capable API with Google Search grounding.
Fallback: Groq Compound with built-in web search.
Optional final fallback: OpenAI Responses API.

This wrapper monkeypatches the legacy generator's call_openai function so the
existing editorial gates, source validation, duplicate checks, JP/EN bundle
creation, and publication contract stay unchanged.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

import requests

import generate_world_frictions as core


def _json_from_text(text: str) -> dict[str, Any]:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", (text or "").strip(), flags=re.I | re.S)
    if not cleaned:
        raise RuntimeError("provider response did not contain output text")
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"provider response was not valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise RuntimeError("provider JSON response must be an object")
    return value


def _synthetic_payload(text: str, urls: list[str]) -> dict[str, Any]:
    sources = [{"url": url} for url in sorted({u for u in urls if isinstance(u, str) and u.startswith("https://")})]
    output: list[dict[str, Any]] = []
    if sources:
        output.append({"type": "web_search_call", "action": {"sources": sources}})
    return {"output_text": text, "output": output}


def _gemini_call(*, instructions: str, input_text: str, max_output_tokens: int, web_search: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not configured")
    model = os.getenv("WORLD_FRICTIONS_GEMINI_MODEL", "gemini-2.5-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body: dict[str, Any] = {
        "systemInstruction": {"parts": [{"text": instructions}]},
        "contents": [{"role": "user", "parts": [{"text": input_text}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "maxOutputTokens": max_output_tokens,
        },
    }
    if web_search:
        body["tools"] = [{"google_search": {}}]

    response = requests.post(
        url,
        timeout=600,
        headers={"x-goog-api-key": key, "Content-Type": "application/json"},
        json=body,
    )
    if not response.ok:
        raise RuntimeError(f"Gemini API failed ({response.status_code}): {response.text[:1000]}")
    payload = response.json()
    candidates = payload.get("candidates") or []
    if not candidates:
        raise RuntimeError("Gemini response did not contain candidates")
    parts = ((candidates[0].get("content") or {}).get("parts") or [])
    text = "\n".join(str(part.get("text", "")) for part in parts if isinstance(part, dict) and part.get("text")).strip()
    urls: list[str] = []
    metadata = candidates[0].get("groundingMetadata") or {}
    for chunk in metadata.get("groundingChunks") or []:
        if not isinstance(chunk, dict):
            continue
        uri = ((chunk.get("web") or {}).get("uri"))
        if isinstance(uri, str):
            urls.append(uri)
    return _json_from_text(text), _synthetic_payload(text, urls)


def _groq_call(*, instructions: str, input_text: str, max_output_tokens: int, web_search: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise RuntimeError("GROQ_API_KEY is not configured")
    model = os.getenv("WORLD_FRICTIONS_GROQ_MODEL", "groq/compound")
    request_text = input_text
    if web_search:
        request_text = (
            "Use built-in web search and visit websites as needed. Return raw JSON only. "
            "Every source URL included in the JSON must come from your actual web research.\n\n" + input_text
        )
    body: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": instructions},
            {"role": "user", "content": request_text},
        ],
        "max_completion_tokens": min(max_output_tokens, 8192),
        "response_format": {"type": "json_object"},
        "citation_options": "enabled",
    }
    if web_search and model.startswith("groq/compound"):
        body["compound_custom"] = {"tools": {"enabled_tools": ["web_search", "visit_website"]}}

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        timeout=600,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Groq-Model-Version": "latest",
        },
        json=body,
    )
    if not response.ok:
        raise RuntimeError(f"Groq API failed ({response.status_code}): {response.text[:1000]}")
    payload = response.json()
    choices = payload.get("choices") or []
    if not choices:
        raise RuntimeError("Groq response did not contain choices")
    message = choices[0].get("message") or {}
    text = str(message.get("content") or "").strip()
    urls: list[str] = []
    for tool in message.get("executed_tools") or []:
        if not isinstance(tool, dict):
            continue
        search_results = tool.get("search_results") or {}
        results = search_results.get("results") if isinstance(search_results, dict) else None
        if not isinstance(results, list):
            continue
        for item in results:
            if isinstance(item, dict) and isinstance(item.get("url"), str):
                urls.append(item["url"])
    return _json_from_text(text), _synthetic_payload(text, urls)


def _openai_call(*, model: str, instructions: str, input_text: str, max_output_tokens: int, web_search: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    return core._ORIGINAL_CALL_OPENAI(
        model=model,
        instructions=instructions,
        input_text=input_text,
        max_output_tokens=max_output_tokens,
        web_search=web_search,
    )


def _provider_chain() -> list[str]:
    raw = os.getenv("WORLD_FRICTIONS_PROVIDER_CHAIN", "gemini,groq,openai")
    return [item.strip().lower() for item in raw.split(",") if item.strip()]


def provider_call_openai(*, model: str, instructions: str, input_text: str, max_output_tokens: int, web_search: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    errors: list[str] = []
    for provider in _provider_chain():
        try:
            if provider == "gemini":
                return _gemini_call(
                    instructions=instructions,
                    input_text=input_text,
                    max_output_tokens=max_output_tokens,
                    web_search=web_search,
                )
            if provider == "groq":
                return _groq_call(
                    instructions=instructions,
                    input_text=input_text,
                    max_output_tokens=max_output_tokens,
                    web_search=web_search,
                )
            if provider == "openai":
                if not os.getenv("OPENAI_API_KEY"):
                    raise RuntimeError("OPENAI_API_KEY is not configured")
                return _openai_call(
                    model=model,
                    instructions=instructions,
                    input_text=input_text,
                    max_output_tokens=max_output_tokens,
                    web_search=web_search,
                )
            errors.append(f"{provider}: unsupported provider")
        except Exception as exc:
            errors.append(f"{provider}: {exc}")
            print(f"PROVIDER_FAIL: {provider}: {exc}")

    reason = "All configured World Frictions providers failed: " + " | ".join(errors)
    core.write_github_output(publish="false", reason=reason, score=0)
    core.write_summary(["## World Frictions provider failure", "", reason])
    raise RuntimeError(reason)


def main() -> int:
    core._ORIGINAL_CALL_OPENAI = core.call_openai
    core.call_openai = provider_call_openai
    return core.main()


if __name__ == "__main__":
    raise SystemExit(main())
