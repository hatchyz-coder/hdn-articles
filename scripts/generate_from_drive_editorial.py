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

# Strongly prefer seeds that fit the current HDN editorial positioning. A broad old
# archive can contain unrelated SEO drafts; those should not crowd out healthcare work.
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
    upper = name.upper()
    if any(term.upper() in upper for term in OFF_BRAND):
        return -100
    return sum(weight for term, weight in KEYWORD_WEIGHTS.items() if term.upper() in upper)


def select_target_doc(drive: Any, state: dict[str, Any], folder_id: str, args: Any, timer: Any):
    with timer.section("driveSeconds", "Drive select editorial seed"):
        # The configured archive folder itself is the approved source scope.
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
            timer.metrics["driveFetched"] = 1
            return doc, "manual_document_id"

        docs, _folders = base.list_recent_seed_docs(drive, folder_id, MAX_SCAN)
        timer.metrics["driveFetched"] = len(docs)
        candidates = [doc for doc in docs if is_unprocessed_or_updated(state, doc)]
        timer.metrics["newDocuments"] = len(candidates)
        candidates.sort(
            key=lambda doc: (relevance_score(str(doc.get("name", ""))), str(doc.get("modifiedTime", ""))),
            reverse=True,
        )
        eligible = [doc for doc in candidates if relevance_score(str(doc.get("name", ""))) >= 0]
        return (eligible[0], "editorial_priority") if eligible else (None, "editorial_priority")


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
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    with timer.section("openaiSeconds", "OpenAI editorial generation with web research"):
        try:
            response = requests.post(
                "https://api.openai.com/v1/responses",
                timeout=(10, 90),
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": os.getenv("OPENAI_MODEL", "gpt-5-mini"),
                    "instructions": instructions,
                    "input": payload_input,
                    "tools": [{"type": "web_search", "search_context_size": "medium"}],
                    "max_output_tokens": 12000,
                    "store": False,
                },
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


def build_article(data: dict[str, Any], doc: dict[str, Any]) -> str:
    description = str(data["description"]).strip()
    if not 60 <= len(description) <= 160:
        raise ValueError(f"description must be 60-160 characters; got {len(description)}")
    tags = [str(tag).strip() for tag in data.get("tags", []) if str(tag).strip()]
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
    description = str(data.get("english_description", "")).strip()
    if not 50 <= len(description) <= 180:
        raise ValueError(f"English description must be 50-180 characters; got {len(description)}")
    tags = [str(tag).strip() for tag in data.get("english_tags", data.get("tags", [])) if str(tag).strip()]
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
