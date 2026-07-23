#!/usr/bin/env python3
"""Generate one draft article from Google Drive 00_KnowledgeBase Google Docs."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import requests
from google.oauth2 import service_account
from googleapiclient.discovery import build

ROOT = Path(__file__).resolve().parents[1]
ARTICLE_DIR = ROOT / "src" / "content" / "articles"
SOCIAL_DIR = ROOT / "social"
EN_DRAFT_DIR = ROOT / "outputs" / "en"
STATE_PATH = ROOT / "data" / "knowledge-base" / "processed-docs.json"
PROMPT_PATH = ROOT / "prompts" / "drive-knowledge-article.md"
REPORT_PATH = ROOT / "data" / "knowledge-base" / "latest-run.json"
MAX_DIRECT_SOURCE_CHARS = 30000
CHUNK_CHARS = 12000

DOC_MIME = "application/vnd.google-apps.document"
FOLDER_MIME = "application/vnd.google-apps.folder"
SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/documents.readonly",
]

ALLOWED_LINKS = [
    {"label": "HDN Japan", "url": "https://hdnjapan.com/"},
    {"label": "自由診療導入支援", "url": "https://hdnjapan.com/self-pay.html"},
    {"label": "LHub", "url": "https://hdnjapan.com/lhub.html"},
    {"label": "無料相談", "url": "https://forms.gle/148jgfSnDgDZ2HsEA"},
]

SENSITIVE_PATTERNS = [
    ("patient_identifier", r"(患者氏名|患者名|カルテ番号|診察券番号|患者ID|患者番号)"),
    ("medical_record_detail", r"(既往歴|服薬歴|検査値|診断名|病歴).{0,40}(氏名|患者|個人|さん|様)"),
    ("email_address", r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}"),
    ("phone_number", r"(?:\+81[-\s]?)?0\d{1,4}[-\s]?\d{1,4}[-\s]?\d{3,4}"),
    ("postal_address", r"(東京都|北海道|大阪府|京都府|.{2,3}県).{0,40}(市|区|町|村).{0,60}(丁目|番地|号)"),
    ("national_id", r"(マイナンバー|個人番号|運転免許証番号|保険証番号)"),
    ("contract_amount", r"(契約金額|見積金額|請求金額|月額|年額|単価|原価|粗利).{0,30}([0-9０-９,，]+|[一二三四五六七八九十百千万億]+)\s*(円|万円|億円)"),
    ("explicit_confidentiality", r"(NDA|秘密保持契約|社外秘|部外秘|confidential|strictly confidential|do not share)"),
    ("credential_secret", r"(パスワード|APIキー|秘密鍵|認証情報|アクセストークン|refresh_token|client_secret)\s*[:：=]"),
    ("named_private_customer", r"(非公開|匿名化前|実名).{0,30}(顧客名|取引先名|会社名|医院名|クリニック名)"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder-id", default=os.getenv("GOOGLE_DRIVE_KNOWLEDGE_FOLDER_ID", ""))
    parser.add_argument("--service-account-json", default=os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", ""))
    parser.add_argument("--exclude-file", type=Path)
    parser.add_argument("--min-score", type=int, default=70)
    parser.add_argument("--state-path", type=Path, default=STATE_PATH)
    parser.add_argument("--report-path", type=Path, default=REPORT_PATH)
    return parser.parse_args()


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_output(name: str, value: str) -> None:
    output_path = os.getenv("GITHUB_OUTPUT")
    value = value.replace("\r", " ").replace("\n", " ")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as handle:
            handle.write(f"{name}={value}\n")
    else:
        print(f"{name}={value}")


def credentials_from_env(raw_json: str) -> service_account.Credentials:
    if not raw_json.strip():
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON is not configured")
    info = json.loads(raw_json)
    return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)


def drive_docs_services(raw_json: str) -> tuple[Any, Any]:
    credentials = credentials_from_env(raw_json)
    drive = build("drive", "v3", credentials=credentials, cache_discovery=False)
    docs = build("docs", "v1", credentials=credentials, cache_discovery=False)
    return drive, docs


def list_children(drive: Any, folder_id: str) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    page_token: str | None = None
    query = (
        f"'{folder_id}' in parents and trashed = false and "
        f"(mimeType = '{FOLDER_MIME}' or mimeType = '{DOC_MIME}')"
    )
    while True:
        response = drive.files().list(
            q=query,
            spaces="drive",
            fields="nextPageToken, files(id, name, mimeType, modifiedTime, webViewLink)",
            pageToken=page_token,
            pageSize=100,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        files.extend(response.get("files", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            return files


def walk_drive(drive: Any, root_folder_id: str) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    stack = [root_folder_id]
    seen_folders: set[str] = set()
    while stack:
        folder_id = stack.pop()
        if folder_id in seen_folders:
            continue
        seen_folders.add(folder_id)
        for item in list_children(drive, folder_id):
            if item.get("mimeType") == FOLDER_MIME:
                stack.append(item["id"])
            elif item.get("mimeType") == DOC_MIME:
                docs.append(item)
    docs.sort(key=lambda item: item.get("modifiedTime", ""), reverse=True)
    return docs


def extract_text_from_doc(docs: Any, document_id: str) -> str:
    document = docs.documents().get(documentId=document_id).execute()
    parts: list[str] = []

    def read_elements(elements: list[dict[str, Any]]) -> None:
        for element in elements:
            paragraph = element.get("paragraph")
            if paragraph:
                line = "".join(
                    run.get("textRun", {}).get("content", "")
                    for run in paragraph.get("elements", [])
                ).strip()
                if line:
                    parts.append(line)
            table = element.get("table")
            if table:
                for row in table.get("tableRows", []):
                    for cell in row.get("tableCells", []):
                        read_elements(cell.get("content", []))

    read_elements(document.get("body", {}).get("content", []))
    return "\n".join(parts)


def existing_source_urls() -> set[str]:
    urls: set[str] = set()
    if not ARTICLE_DIR.exists():
        return urls
    pattern = re.compile(r'^sourceUrl:\s*["\']?([^"\'\n]+)', re.MULTILINE)
    for path in ARTICLE_DIR.glob("*.md"):
        match = pattern.search(path.read_text(encoding="utf-8"))
        if match:
            urls.add(match.group(1).strip())
    return urls


def excluded_tokens(path: Path | None) -> set[str]:
    if not path or not path.exists():
        return set()
    return {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}


def confidentiality_flags(name: str, text: str) -> list[str]:
    target = f"{name}\n{text}"
    return [label for label, pattern in SENSITIVE_PATTERNS if re.search(pattern, target, re.I)]


def valid_slug(value: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value))


def fallback_slug(file_id: str) -> str:
    return f"knowledge-base-{file_id[:10].lower()}"


def normalize_slug(value: str, file_id: str) -> str:
    slug = re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-")
    slug = re.sub(r"-+", "-", slug)
    return slug if valid_slug(slug) else fallback_slug(file_id)


def chunk_text(text: str, chunk_chars: int = CHUNK_CHARS) -> list[str]:
    paragraphs = [line.strip() for line in text.splitlines() if line.strip()]
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for paragraph in paragraphs:
        if len(paragraph) > chunk_chars:
            if current:
                chunks.append("\n".join(current))
                current = []
                current_len = 0
            for start in range(0, len(paragraph), chunk_chars):
                chunks.append(paragraph[start:start + chunk_chars])
            continue
        if current and current_len + len(paragraph) + 1 > chunk_chars:
            chunks.append("\n".join(current))
            current = []
            current_len = 0
        current.append(paragraph)
        current_len += len(paragraph) + 1
    if current:
        chunks.append("\n".join(current))
    return chunks or [text[:chunk_chars]]


def response_text(payload: dict[str, Any]) -> str:
    output_text = payload.get("output_text")
    if output_text:
        return output_text
    chunks: list[str] = []
    for item in payload.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                chunks.append(content.get("text", ""))
    return "\n".join(chunks)


def call_openai_json(instructions: str, user_input: dict[str, Any], max_output_tokens: int) -> dict[str, Any]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    response = requests.post(
        "https://api.openai.com/v1/responses",
        timeout=180,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": os.getenv("OPENAI_MODEL", "gpt-5-mini"),
            "instructions": instructions,
            "input": json.dumps(user_input, ensure_ascii=False),
            "max_output_tokens": max_output_tokens,
            "store": False,
        },
    )
    response.raise_for_status()
    output_text = response_text(response.json())
    output_text = re.sub(r"^```(?:json)?\s*|\s*```$", "", (output_text or "").strip(), flags=re.I | re.S)
    if not output_text:
        raise RuntimeError("OpenAI response did not contain output text")
    return json.loads(output_text)


def summarize_long_source(doc: dict[str, Any], text: str) -> tuple[str, dict[str, Any]]:
    chunks = chunk_text(text)
    if len(text) <= MAX_DIRECT_SOURCE_CHARS and len(chunks) == 1:
        return text, {
            "mode": "full_text",
            "sourceTextCharacters": len(text),
            "chunks": 1,
            "note": "Full Google Docs body was sent to the article evaluator.",
        }

    instructions = (
        "Summarize this Google Docs chunk for later Japanese article evaluation. "
        "Preserve concrete facts, operational insights, uncertainties, safety concerns, "
        "claims that need official-source verification, and potential confidential details. "
        "Do not add facts. Return JSON only with summary, key_points, risks, verification_needed, unsupported_claims."
    )
    summaries: list[dict[str, Any]] = []
    for index, chunk in enumerate(chunks, start=1):
        summaries.append(call_openai_json(
            instructions,
            {
                "document": {"name": doc["name"], "file_id": doc["id"]},
                "chunk_index": index,
                "chunk_count": len(chunks),
                "chunk_text": chunk,
            },
            2500,
        ))
    combined = {
        "document_name": doc["name"],
        "source_text_was_chunk_summarized": True,
        "source_text_characters": len(text),
        "chunk_count": len(chunks),
        "chunk_summaries": summaries,
    }
    return json.dumps(combined, ensure_ascii=False), {
        "mode": "chunk_summarized",
        "sourceTextCharacters": len(text),
        "chunks": len(chunks),
        "chunkCharacters": CHUNK_CHARS,
        "note": (
            "Google Docs text exceeded the direct evaluation limit. The script split it "
            "into chunks and sent AI-generated chunk summaries to the article evaluator."
        ),
    }


def call_openai(doc: dict[str, Any], text: str) -> tuple[dict[str, Any], dict[str, Any]]:
    source_text, source_processing = summarize_long_source(doc, text)
    instructions = PROMPT_PATH.read_text(encoding="utf-8")
    user_input = {
        "document": {
            "name": doc["name"],
            "file_id": doc["id"],
            "url": doc.get("webViewLink"),
            "modified_time": doc.get("modifiedTime"),
        },
        "source_text": source_text,
        "source_processing": source_processing,
        "official_source_research_extension": official_source_extension(),
        "allowed_links": ALLOWED_LINKS,
    }
    return call_openai_json(instructions, user_input, 8000), source_processing


def official_source_extension() -> dict[str, Any]:
    return {
        "status": "prepared_not_auto_cited",
        "candidate_sources": [
            "厚生労働省",
            "PMDA",
            "消費者庁",
            "デジタル庁",
            "総務省",
            "経済産業省",
            "公正取引委員会",
            "個人情報保護委員会",
            "関連学会",
            "各企業公式情報",
        ],
        "required_outputs": [
            "additional_verification_topics",
            "official_source_candidates",
            "unsupported_claims_from_source_only",
        ],
    }


def yaml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def build_article(data: dict[str, Any], doc: dict[str, Any]) -> str:
    description = str(data["description"]).strip()
    if not 60 <= len(description) <= 160:
        raise ValueError(f"description must be 60-160 characters; got {len(description)}")

    tags = [str(tag).strip() for tag in data.get("tags", []) if str(tag).strip()]
    faq = data.get("faq", [])
    references = data.get("references", [])
    cta = str(data.get("cta", "consultation")).strip()
    if cta not in {"consultation", "lhub", "self-pay"}:
        cta = "consultation"

    lines = [
        "---",
        f"title: {yaml_string(str(data['title']).strip())}",
        f"description: {yaml_string(description)}",
        f"publishedAt: {date.today().isoformat()}",
        f"updatedAt: {date.today().isoformat()}",
        f"category: {yaml_string(str(data.get('category') or '医療経営'))}",
        "tags:",
    ]
    lines.extend(f"  - {yaml_string(tag)}" for tag in tags)
    lines.extend([
        'author: "羽田野 剛士"',
        "draft: true",
        "featured: false",
        f"sourceUrl: {yaml_string(str(doc.get('webViewLink') or 'https://docs.google.com/document/d/' + doc['id']))}",
        f"cta: {cta}",
        "---",
        "",
        str(data.get("summary", "")).strip(),
        "",
        str(data["body_markdown"]).strip(),
        "",
        "## よくある質問",
        "",
    ])
    for item in faq[:5]:
        lines.extend([
            f"### {str(item.get('question', '')).strip()}",
            "",
            str(item.get("answer", "")).strip(),
            "",
        ])
    lines.extend([
        "## 参考情報",
        "",
        f"- 元文書: [{doc['name']}]({doc.get('webViewLink') or 'https://docs.google.com/document/d/' + doc['id']})",
        f"- 元文書更新日: {doc.get('modifiedTime', '')}",
    ])
    for item in references:
        url = str(item.get("url", "")).strip()
        label = str(item.get("label", "")).strip()
        if url and label and any(url == allowed["url"] for allowed in ALLOWED_LINKS):
            lines.append(f"- [{label}]({url})")
    lines.extend([
        "",
        "## 更新日・著者",
        "",
        f"- 更新日: {date.today().isoformat()}",
        "- 著者: 羽田野 剛士",
        "",
        "> この記事は社内ナレッジをもとに、機密情報を除外して記事下書き化したものです。公開前に事実関係、広告表現、法務・医療上の妥当性を必ず確認してください。",
        "",
    ])
    return "\n".join(lines)


def write_outputs(slug: str, data: dict[str, Any], article: str) -> list[Path]:
    ARTICLE_DIR.mkdir(parents=True, exist_ok=True)
    social_path = SOCIAL_DIR / slug
    social_path.mkdir(parents=True, exist_ok=True)
    EN_DRAFT_DIR.mkdir(parents=True, exist_ok=True)
    article_path = ARTICLE_DIR / f"{slug}.md"
    if article_path.exists():
        raise FileExistsError(f"Article already exists: {article_path}")
    article_path.write_text(article, encoding="utf-8")
    outputs = [article_path]
    for filename, key in {
        "x.md": "social_x",
        "facebook.md": "social_facebook",
        "linkedin.md": "social_linkedin",
    }.items():
        path = social_path / filename
        path.write_text(str(data.get(key, "")).strip() + "\n", encoding="utf-8")
        outputs.append(path)
    en_path = EN_DRAFT_DIR / f"{slug}.md"
    en_path.write_text(
        "\n".join([
            f"# {str(data.get('english_title', '')).strip()}",
            "",
            str(data.get("english_description", "")).strip(),
            "",
            str(data.get("english_summary", "")).strip(),
            "",
            "> English draft for editorial review. Not published automatically.",
            "",
        ]),
        encoding="utf-8",
    )
    outputs.append(en_path)
    return outputs


def update_state(state: dict[str, Any], doc: dict[str, Any], status: str, detail: dict[str, Any]) -> None:
    state.setdefault("documents", {})[doc["id"]] = {
        "name": doc["name"],
        "url": doc.get("webViewLink"),
        "modifiedTime": doc.get("modifiedTime"),
        "processedAt": datetime.now(timezone.utc).isoformat(),
        "status": status,
        **detail,
    }
    state["updatedAt"] = datetime.now(timezone.utc).isoformat()


def main() -> int:
    args = parse_args()
    if not args.folder_id:
        raise RuntimeError("GOOGLE_DRIVE_KNOWLEDGE_FOLDER_ID is not configured")

    drive, docs = drive_docs_services(args.service_account_json)
    state = load_json(args.state_path, {"documents": {}})
    used_sources = existing_source_urls()
    excluded = excluded_tokens(args.exclude_file)
    run_log: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []

    for doc in walk_drive(drive, args.folder_id):
        doc_url = doc.get("webViewLink") or f"https://docs.google.com/document/d/{doc['id']}"
        previous = state.get("documents", {}).get(doc["id"])
        if previous and previous.get("modifiedTime") == doc.get("modifiedTime"):
            continue
        if doc_url in used_sources or doc["id"] in excluded or doc_url in excluded:
            run_log.append({"fileId": doc["id"], "name": doc["name"], "status": "skipped_duplicate"})
            continue

        text = extract_text_from_doc(docs, doc["id"])
        if len(text) < 500:
            reason = "document text is too short to support a reliable article"
            update_state(state, doc, "skipped", {"reason": reason})
            run_log.append({"fileId": doc["id"], "name": doc["name"], "status": "skipped", "reason": reason})
            continue

        flags = confidentiality_flags(doc["name"], text)
        if flags:
            reason = "confidentiality heuristic matched: " + ", ".join(flags)
            update_state(state, doc, "skipped_confidential", {"reason": reason, "flags": flags})
            run_log.append({"fileId": doc["id"], "name": doc["name"], "status": "skipped_confidential", "reason": reason})
            continue

        data, source_processing = call_openai(doc, text)
        ai_flags = [str(flag) for flag in data.get("confidentiality_flags", []) if str(flag).strip()]
        score = int(data.get("score", 0))
        if not data.get("should_generate") or score < args.min_score or ai_flags:
            reason = str(data.get("skip_reason") or f"AI score {score} below threshold or safety flags present")
            update_state(state, doc, "skipped", {"reason": reason, "score": score, "eeat": data.get("eeat", {}), "flags": ai_flags, "sourceProcessing": source_processing})
            run_log.append({"fileId": doc["id"], "name": doc["name"], "status": "skipped", "reason": reason, "score": score})
            continue

        candidates.append({"doc": doc, "url": doc_url, "data": data, "score": score, "sourceProcessing": source_processing})
        run_log.append({"fileId": doc["id"], "name": doc["name"], "status": "scored", "score": score})

    if candidates:
        selected = max(candidates, key=lambda item: item["score"])
        doc = selected["doc"]
        data = selected["data"]
        score = selected["score"]
        doc_url = selected["url"]
        source_processing = selected["sourceProcessing"]
        slug = normalize_slug(str(data.get("suggested_slug", "")), doc["id"])
        article = build_article(data, doc)
        outputs = write_outputs(slug, data, article)
        research_review = {
            "additionalVerificationTopics": data.get("additional_verification_topics", []),
            "officialSourceCandidates": data.get("official_source_candidates", []),
            "unsupportedClaimsFromSourceOnly": data.get("unsupported_claims_from_source_only", []),
        }
        update_state(state, doc, "generated", {"slug": slug, "score": score, "eeat": data.get("eeat", {}), "sourceProcessing": source_processing, "researchReview": research_review})
        write_json(args.state_path, state)
        report = {
            "selected": True,
            "fileId": doc["id"],
            "name": doc["name"],
            "url": doc_url,
            "modifiedTime": doc.get("modifiedTime"),
            "slug": slug,
            "score": score,
            "eeat": data.get("eeat", {}),
            "sourceProcessing": source_processing,
            "researchReview": research_review,
            "outputs": [str(path.relative_to(ROOT)) for path in outputs],
            "runLog": run_log,
        }
        write_json(args.report_path, report)
        write_output("selected", "true")
        write_output("slug", slug)
        write_output("file_id", doc["id"])
        write_output("source_url", doc_url)
        write_output("source_name", doc["name"])
        write_output("modified_time", str(doc.get("modifiedTime", "")))
        write_output("score", str(score))
        write_output("eeat", json.dumps(data.get("eeat", {}), ensure_ascii=False))
        write_output("research_review", json.dumps(research_review, ensure_ascii=False))
        print(f"Generated one article draft from {doc['name']}: {slug}")
        return 0

    write_json(args.state_path, state)
    write_json(args.report_path, {"selected": False, "runLog": run_log, "officialSourceResearchExtension": official_source_extension()})
    write_output("selected", "false")
    write_output("reason", "no eligible new or updated Google Docs document")
    print("No eligible new or updated Google Docs document was generated.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
