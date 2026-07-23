#!/usr/bin/env python3
"""Generate at most one draft article from the newest changed Google Drive Doc."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import requests

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
except ModuleNotFoundError:
    service_account = None
    build = None

ROOT = Path(__file__).resolve().parents[1]
ARTICLE_DIR = ROOT / "src" / "content" / "articles"
SOCIAL_DIR = ROOT / "social"
EN_DRAFT_DIR = ROOT / "outputs" / "en"
STATE_PATH = ROOT / "data" / "knowledge-base" / "processed-docs.json"
REPORT_PATH = ROOT / "data" / "knowledge-base" / "latest-run.json"
PROMPT_PATH = ROOT / "prompts" / "drive-knowledge-article.md"

DOC_MIME = "application/vnd.google-apps.document"
FOLDER_MIME = "application/vnd.google-apps.folder"
SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/documents.readonly",
]
OPENAI_TIMEOUT = (10, 45)
MAX_SEED_FILES = 5
MAX_INPUT_CHARS = 12000
MAX_RETRIES = 2

SOURCE_TYPES = {
    DOC_MIME: {"kind": "google_doc", "enabled": True},
    "application/pdf": {"kind": "pdf", "enabled": False},
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {"kind": "docx", "enabled": False},
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": {"kind": "pptx", "enabled": False},
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {"kind": "xlsx", "enabled": False},
    "text/markdown": {"kind": "markdown", "enabled": False},
    "text/plain": {"kind": "text", "enabled": False},
}

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
    parser.add_argument("--max-drive-files", type=int, default=MAX_SEED_FILES)
    parser.add_argument("--document-id", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--mock-openai-timeout", action="store_true")
    return parser.parse_args()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_output(name: str, value: str) -> None:
    value = str(value).replace("\r", " ").replace("\n", " ")
    output_path = os.getenv("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as handle:
            handle.write(f"{name}={value}\n")
    else:
        print(f"{name}={value}", flush=True)


class RunTimer:
    def __init__(self) -> None:
        self.started = time.monotonic()
        self.metrics: dict[str, Any] = {
            "selectedDocumentId": "",
            "selectedDocumentName": "",
            "driveFetched": 0,
            "newDocuments": 0,
            "aiEvaluations": 0,
            "articlesGenerated": 0,
            "apiCalls": 0,
            "inputCharacters": 0,
            "openaiSeconds": 0.0,
            "driveSeconds": 0.0,
            "docsFetchSeconds": 0.0,
            "stateSaveSeconds": 0.0,
            "fileIoSeconds": 0.0,
            "executionSeconds": 0.0,
            "exitReason": "",
        }

    def section(self, key: str, label: str):
        return TimedSection(self, key, label)

    def add(self, key: str, value: float | int) -> None:
        self.metrics[key] = round(float(self.metrics.get(key, 0)) + float(value), 2)

    def finish(self, reason: str) -> None:
        self.metrics["exitReason"] = reason
        self.metrics["executionSeconds"] = round(time.monotonic() - self.started, 2)


class TimedSection:
    def __init__(self, timer: RunTimer, key: str, label: str) -> None:
        self.timer = timer
        self.key = key
        self.label = label
        self.started = 0.0

    def __enter__(self):
        self.started = time.monotonic()
        print(f"START {self.label} at {now_iso()}", flush=True)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        elapsed = time.monotonic() - self.started
        self.timer.add(self.key, elapsed)
        print(f"END {self.label} at {now_iso()} elapsed={elapsed:.2f}s", flush=True)


def credentials_from_env(raw_json: str) -> service_account.Credentials:
    if service_account is None:
        raise RuntimeError("google-auth and google-api-python-client are required")
    if not raw_json.strip():
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON is not configured")
    return service_account.Credentials.from_service_account_info(json.loads(raw_json), scopes=SCOPES)


def google_services(raw_json: str) -> tuple[Any, Any]:
    if build is None:
        raise RuntimeError("google-api-python-client is required")
    credentials = credentials_from_env(raw_json)
    drive = build("drive", "v3", credentials=credentials, cache_discovery=False)
    docs = build("docs", "v1", credentials=credentials, cache_discovery=False)
    return drive, docs


def enabled_source_mime_types() -> set[str]:
    return {mime for mime, config in SOURCE_TYPES.items() if config.get("enabled")}


def drive_cache(state: dict[str, Any], root_folder_id: str) -> dict[str, Any]:
    cache = state.setdefault("driveCache", {})
    folder_ids = set(cache.get("folderIds", []))
    folder_ids.add(root_folder_id)
    cache["folderIds"] = sorted(folder_ids)
    cache.setdefault("documents", {})
    return cache


def get_start_page_token(drive: Any) -> str:
    return drive.changes().getStartPageToken(supportsAllDrives=True).execute()["startPageToken"]


def list_recent_seed_docs(drive: Any, folder_id: str, limit: int) -> list[dict[str, Any]]:
    response = drive.files().list(
        q=f"'{folder_id}' in parents and trashed = false and mimeType = '{DOC_MIME}'",
        spaces="drive",
        fields="files(id,name,mimeType,modifiedTime,webViewLink,parents)",
        orderBy="modifiedTime desc",
        pageSize=limit,
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute()
    return response.get("files", [])


def list_changed_docs(drive: Any, cache: dict[str, Any], root_folder_id: str, limit: int) -> tuple[list[dict[str, Any]], str]:
    token = cache.get("changePageToken")
    if not token:
        cache["changePageToken"] = get_start_page_token(drive)
        return list_recent_seed_docs(drive, root_folder_id, limit), "bounded_seed"

    folder_ids = set(cache.get("folderIds", [root_folder_id]))
    enabled_mimes = enabled_source_mime_types()
    docs_by_id: dict[str, dict[str, Any]] = {}
    response = drive.changes().list(
        pageToken=token,
        spaces="drive",
        fields="nextPageToken,newStartPageToken,changes(removed,file(id,name,mimeType,modifiedTime,webViewLink,parents,trashed))",
        pageSize=50,
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute()
    for change in response.get("changes", []):
        item = change.get("file") or {}
        if change.get("removed") or item.get("trashed"):
            cache.get("documents", {}).pop(item.get("id", ""), None)
            continue
        parents = set(item.get("parents", []))
        if item.get("mimeType") == FOLDER_MIME and parents & folder_ids:
            folder_ids.add(item["id"])
        elif item.get("mimeType") in enabled_mimes and parents & folder_ids:
            docs_by_id[item["id"]] = item
    cache["folderIds"] = sorted(folder_ids)
    cache["changePageToken"] = response.get("newStartPageToken") or response.get("nextPageToken") or token
    docs = sorted(docs_by_id.values(), key=lambda item: item.get("modifiedTime", ""), reverse=True)[:limit]
    return docs, "changes"


def get_doc_metadata(drive: Any, document_id: str) -> dict[str, Any]:
    return drive.files().get(
        fileId=document_id,
        fields="id,name,mimeType,modifiedTime,webViewLink,parents",
        supportsAllDrives=True,
    ).execute()


def existing_source_urls() -> set[str]:
    urls: set[str] = set()
    pattern = re.compile(r'^sourceUrl:\s*["\']?([^"\'\n]+)', re.MULTILINE)
    for path in ARTICLE_DIR.glob("*.md") if ARTICLE_DIR.exists() else []:
        match = pattern.search(path.read_text(encoding="utf-8"))
        if match:
            urls.add(match.group(1).strip())
    return urls


def excluded_tokens(path: Path | None) -> set[str]:
    if not path or not path.exists():
        return set()
    return {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}


def document_record(state: dict[str, Any], doc_id: str) -> dict[str, Any]:
    return state.setdefault("documents", {}).setdefault(doc_id, {})


def retry_count(record: dict[str, Any]) -> int:
    return int(record.get("retry_count", 0))


def is_unprocessed_or_updated(state: dict[str, Any], doc: dict[str, Any]) -> bool:
    record = state.get("documents", {}).get(doc["id"])
    if not record:
        return True
    if record.get("status") in {"processing", "api_timeout", "os_timeout", "dry_run"} and retry_count(record) <= MAX_RETRIES:
        return True
    return record.get("modifiedTime") != doc.get("modifiedTime")


def select_target_doc(drive: Any, state: dict[str, Any], folder_id: str, args: argparse.Namespace, timer: RunTimer) -> tuple[dict[str, Any] | None, str]:
    with timer.section("driveSeconds", "Drive select target document"):
        if args.document_id:
            doc = get_doc_metadata(drive, args.document_id)
            timer.metrics["driveFetched"] = 1
            return doc, "manual_document_id"

        cache = drive_cache(state, folder_id)
        docs, mode = list_changed_docs(drive, cache, folder_id, min(args.max_drive_files, MAX_SEED_FILES))
        timer.metrics["driveFetched"] = len(docs)
        for doc in docs:
            cache.setdefault("documents", {})[doc["id"]] = {
                "name": doc.get("name"),
                "modifiedTime": doc.get("modifiedTime"),
                "url": doc.get("webViewLink"),
                "parents": doc.get("parents", []),
                "seenAt": now_iso(),
            }
        candidates = [doc for doc in docs if is_unprocessed_or_updated(state, doc)]
        timer.metrics["newDocuments"] = len(candidates)
        return (candidates[0], mode) if candidates else (None, mode)


def mark_started(state: dict[str, Any], doc: dict[str, Any]) -> None:
    record = document_record(state, doc["id"])
    record.update({
        "name": doc.get("name"),
        "url": doc.get("webViewLink"),
        "modifiedTime": doc.get("modifiedTime"),
        "status": "processing",
        "startedAt": now_iso(),
        "retry_count": retry_count(record),
    })
    state["updatedAt"] = now_iso()


def mark_finished(state: dict[str, Any], doc: dict[str, Any], status: str, detail: dict[str, Any], permanent: bool) -> None:
    record = document_record(state, doc["id"])
    next_retry = retry_count(record)
    if not permanent:
        next_retry += 1
    record.update({
        "name": doc.get("name"),
        "url": doc.get("webViewLink"),
        "modifiedTime": doc.get("modifiedTime"),
        "status": status,
        "finishedAt": now_iso(),
        "retry_count": next_retry,
        **detail,
    })
    state["updatedAt"] = now_iso()


def save_state_and_report(args: argparse.Namespace, state: dict[str, Any], report: dict[str, Any], timer: RunTimer) -> None:
    started = time.monotonic()
    print(f"START state and latest-run save at {now_iso()}", flush=True)
    write_json(args.state_path, state)
    timer.add("stateSaveSeconds", time.monotonic() - started)
    report["metrics"] = timer.metrics
    write_json(args.report_path, report)
    elapsed = time.monotonic() - started
    timer.metrics["stateSaveSeconds"] = round(elapsed, 2)
    report["metrics"] = timer.metrics
    write_json(args.report_path, report)
    print(f"END state and latest-run save at {now_iso()} elapsed={elapsed:.2f}s", flush=True)


def write_all_outputs(metrics: dict[str, Any], selected: bool, reason: str = "") -> None:
    write_output("selected", "true" if selected else "false")
    if reason:
        write_output("reason", reason)
    for key, value in metrics.items():
        write_output(key, value)


def confidentiality_flags(name: str, text: str) -> list[str]:
    target = f"{name}\n{text}"
    return [label for label, pattern in SENSITIVE_PATTERNS if re.search(pattern, target, re.I)]


def extract_text_from_doc(docs: Any, document_id: str) -> str:
    document = docs.documents().get(documentId=document_id).execute()
    parts: list[str] = []

    def read_elements(elements: list[dict[str, Any]]) -> None:
        for element in elements:
            paragraph = element.get("paragraph")
            if paragraph:
                line = "".join(run.get("textRun", {}).get("content", "") for run in paragraph.get("elements", [])).strip()
                if line:
                    parts.append(line)
            table = element.get("table")
            if table:
                for row in table.get("tableRows", []):
                    for cell in row.get("tableCells", []):
                        read_elements(cell.get("content", []))

    read_elements(document.get("body", {}).get("content", []))
    return "\n".join(parts)


def select_input_text(text: str) -> tuple[str, dict[str, Any]]:
    if len(text) <= MAX_INPUT_CHARS:
        return text, {"mode": "full_text", "sourceTextCharacters": len(text), "inputCharacters": len(text)}
    chunk_size = 4000
    midpoint = max(0, len(text) // 2 - chunk_size // 2)
    tail = max(0, len(text) - chunk_size)
    parts = [
        {"position": "beginning", "text": text[:chunk_size]},
        {"position": "middle", "text": text[midpoint:midpoint + chunk_size]},
        {"position": "ending", "text": text[tail:]},
    ]
    sampled = json.dumps({"sampled_source_text": parts}, ensure_ascii=False)
    return sampled, {
        "mode": "sampled_beginning_middle_ending",
        "sourceTextCharacters": len(text),
        "inputCharacters": len(sampled),
        "chunks": 3,
    }


def call_openai_once(doc: dict[str, Any], source_text: str, source_processing: dict[str, Any], timer: RunTimer, mock_timeout: bool) -> dict[str, Any]:
    instructions = PROMPT_PATH.read_text(encoding="utf-8")
    user_input = {
        "document": {
            "name": doc.get("name"),
            "file_id": doc.get("id"),
            "url": doc.get("webViewLink"),
            "modified_time": doc.get("modifiedTime"),
        },
        "source_text": source_text,
        "source_processing": source_processing,
        "allowed_links": ALLOWED_LINKS,
        "external_writer": {"draft_author": "成松 義昭", "public_author": "羽田野 剛士"},
    }
    payload_input = json.dumps(user_input, ensure_ascii=False)
    timer.metrics["apiCalls"] = 1
    timer.metrics["aiEvaluations"] = 1
    timer.metrics["inputCharacters"] = len(payload_input) + len(instructions)
    if mock_timeout:
        with timer.section("openaiSeconds", "OpenAI mock timeout"):
            raise TimeoutError("OpenAI mock timed out")
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    with timer.section("openaiSeconds", "OpenAI single evaluation/generation call"):
        try:
            response = requests.post(
                "https://api.openai.com/v1/responses",
                timeout=OPENAI_TIMEOUT,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": os.getenv("OPENAI_MODEL", "gpt-5-mini"),
                    "instructions": instructions,
                    "input": payload_input,
                    "max_output_tokens": 8000,
                    "store": False,
                },
            )
        except requests.Timeout as exc:
            raise TimeoutError("OpenAI API timed out after connect/read timeout") from exc
    response.raise_for_status()
    output_text = response.json().get("output_text", "")
    if not output_text:
        chunks: list[str] = []
        for item in response.json().get("output", []):
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    chunks.append(content.get("text", ""))
        output_text = "\n".join(chunks)
    output_text = re.sub(r"^```(?:json)?\s*|\s*```$", "", output_text.strip(), flags=re.I | re.S)
    return json.loads(output_text)


def yaml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def normalize_slug(value: str, file_id: str) -> str:
    slug = re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-")
    slug = re.sub(r"-+", "-", slug)
    if re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        return slug
    return f"knowledge-base-{file_id[:10].lower()}"


def build_article(data: dict[str, Any], doc: dict[str, Any]) -> str:
    description = str(data["description"]).strip()
    if not 60 <= len(description) <= 160:
        raise ValueError(f"description must be 60-160 characters; got {len(description)}")
    tags = [str(tag).strip() for tag in data.get("tags", []) if str(tag).strip()]
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
        'editorialSourceAuthor: "成松 義昭"',
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
    for item in data.get("faq", [])[:5]:
        lines.extend([f"### {str(item.get('question', '')).strip()}", "", str(item.get("answer", "")).strip(), ""])
    lines.extend([
        "## 参考情報",
        "",
        f"- 元文書: [{doc['name']}]({doc.get('webViewLink') or 'https://docs.google.com/document/d/' + doc['id']})",
        f"- 元文書更新日: {doc.get('modifiedTime', '')}",
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
    for filename, key in {"x.md": "social_x", "facebook.md": "social_facebook", "linkedin.md": "social_linkedin"}.items():
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


def finish(args: argparse.Namespace, state: dict[str, Any], report: dict[str, Any], timer: RunTimer, selected: bool, reason: str) -> int:
    timer.finish(reason)
    save_state_and_report(args, state, report, timer)
    write_all_outputs(timer.metrics, selected, reason)
    print(f"FINISH {reason} total={timer.metrics['executionSeconds']}s", flush=True)
    return 0


def main() -> int:
    args = parse_args()
    timer = RunTimer()
    state = load_json(args.state_path, {"documents": {}})
    report: dict[str, Any] = {"selected": False, "runLog": [], "createdAt": now_iso()}
    if not args.folder_id and not args.document_id:
        raise RuntimeError("GOOGLE_DRIVE_KNOWLEDGE_FOLDER_ID or --document-id is required")

    with timer.section("driveSeconds", "Google API client setup"):
        drive, docs = google_services(args.service_account_json)

    doc, mode = select_target_doc(drive, state, args.folder_id, args, timer)
    report["selectionMode"] = mode
    if not doc:
        return finish(args, state, report, timer, False, "no_candidate")

    timer.metrics["selectedDocumentId"] = doc["id"]
    timer.metrics["selectedDocumentName"] = doc.get("name", "")
    report.update({"fileId": doc["id"], "name": doc.get("name"), "url": doc.get("webViewLink"), "modifiedTime": doc.get("modifiedTime")})

    doc_url = doc.get("webViewLink") or f"https://docs.google.com/document/d/{doc['id']}"
    if doc_url in existing_source_urls() or doc["id"] in excluded_tokens(args.exclude_file) or doc_url in excluded_tokens(args.exclude_file):
        return finish(args, state, report, timer, False, "duplicate_source")

    record = document_record(state, doc["id"])
    if retry_count(record) > MAX_RETRIES:
        mark_finished(state, doc, "manual_review", {"reason": "retry_count exceeded", "manualReview": True}, permanent=True)
        return finish(args, state, report, timer, False, "manual_review_retry_limit")

    mark_started(state, doc)
    save_state_and_report(args, state, {**report, "reason": "processing_started"}, timer)

    with timer.section("docsFetchSeconds", "Google Docs body fetch"):
        text = extract_text_from_doc(docs, doc["id"])
    source_text, source_processing = select_input_text(text)
    report["sourceProcessing"] = source_processing

    flags = confidentiality_flags(doc.get("name", ""), source_text)
    if flags:
        mark_finished(state, doc, "skipped_confidential", {"reason": "confidentiality heuristic matched", "flags": flags}, permanent=True)
        return finish(args, state, {**report, "flags": flags}, timer, False, "confidential")

    if args.dry_run:
        mark_finished(state, doc, "dry_run", {"reason": "dry_run completed", "sourceProcessing": source_processing}, permanent=False)
        return finish(args, state, report, timer, False, "dry_run")

    try:
        data = call_openai_once(doc, source_text, source_processing, timer, args.mock_openai_timeout)
    except TimeoutError as exc:
        mark_finished(state, doc, "api_timeout", {"reason": str(exc), "sourceProcessing": source_processing}, permanent=False)
        return finish(args, state, report, timer, False, "api_timeout")

    score = int(data.get("score", 0))
    ai_flags = [str(flag) for flag in data.get("confidentiality_flags", []) if str(flag).strip()]
    if ai_flags:
        mark_finished(state, doc, "skipped_confidential", {"reason": "AI confidentiality flags", "flags": ai_flags, "score": score}, permanent=True)
        return finish(args, state, {**report, "score": score, "flags": ai_flags}, timer, False, "confidential")
    if not data.get("should_generate") or score < args.min_score:
        mark_finished(state, doc, "low_score", {"reason": data.get("skip_reason", "low score"), "score": score}, permanent=True)
        return finish(args, state, {**report, "score": score}, timer, False, "low_score")

    slug = normalize_slug(str(data.get("suggested_slug", "")), doc["id"])
    outputs = write_outputs(slug, data, build_article(data, doc))
    research_review = {
        "additionalVerificationTopics": data.get("additional_verification_topics", []),
        "officialSourceCandidates": data.get("official_source_candidates", []),
        "unsupportedClaimsFromSourceOnly": data.get("unsupported_claims_from_source_only", []),
    }
    mark_finished(state, doc, "generated", {"slug": slug, "score": score, "researchReview": research_review, "sourceProcessing": source_processing}, permanent=True)
    timer.metrics["articlesGenerated"] = 1
    report.update({
        "selected": True,
        "slug": slug,
        "score": score,
        "eeat": data.get("eeat", {}),
        "researchReview": research_review,
        "outputs": [str(path.relative_to(ROOT)) for path in outputs],
    })
    write_output("slug", slug)
    write_output("file_id", doc["id"])
    write_output("source_url", doc_url)
    write_output("source_name", doc.get("name", ""))
    write_output("modified_time", str(doc.get("modifiedTime", "")))
    write_output("score", str(score))
    write_output("eeat", json.dumps(data.get("eeat", {}), ensure_ascii=False))
    write_output("research_review", json.dumps(research_review, ensure_ascii=False))
    return finish(args, state, report, timer, True, "generated")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        raise SystemExit(1)
