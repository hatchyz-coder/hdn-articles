#!/usr/bin/env python3
"""Load bounded, sanitized Google Drive context for article generation.

Configured folders are private editorial references only. This module never writes
Drive file IDs, folder IDs, URLs, titles, or raw document bodies to repository state.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
except ModuleNotFoundError:
    service_account = None
    build = None

DOC_MIME = "application/vnd.google-apps.document"
FOLDER_MIME = "application/vnd.google-apps.folder"
SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/documents.readonly",
]
MAX_FOLDERS = 100
MAX_DOCS_SCANNED = 120
MAX_SELECTED_PER_SOURCE = 2
MAX_CHARS_PER_DOC = 2200

SENSITIVE_REPLACEMENTS = [
    (re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I), "[email omitted]"),
    (re.compile(r"(?:\+81[-\s]?)?0\d{1,4}[-\s]?\d{1,4}[-\s]?\d{3,4}"), "[phone omitted]"),
    (re.compile(r"(契約金額|見積金額|請求金額|月額|年額|単価|原価|粗利)\s*[:：]?\s*[0-9０-９,，]+\s*(円|万円|億円)"), "[commercial amount omitted]"),
    (re.compile(r"(パスワード|APIキー|秘密鍵|アクセストークン|refresh_token|client_secret)\s*[:：=]\s*\S+", re.I), "[credential omitted]"),
]

PRIVATE_NAME_HINTS = re.compile(r"(議事録|定例|MTG|ミーティング|アジェンダ|見積|提案書|運用マニュアル|プロジェクト|進捗報告)", re.I)
TOKEN_RE = re.compile(r"[A-Za-z0-9]{3,}|[一-龠々ぁ-んァ-ヶー]{2,}")


def _credentials(raw_json: str):
    if service_account is None or build is None:
        raise RuntimeError("Google API libraries are unavailable")
    if not raw_json.strip():
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON is not configured")
    return service_account.Credentials.from_service_account_info(json.loads(raw_json), scopes=SCOPES)


def _services(raw_json: str) -> tuple[Any, Any]:
    credentials = _credentials(raw_json)
    return (
        build("drive", "v3", credentials=credentials, cache_discovery=False),
        build("docs", "v1", credentials=credentials, cache_discovery=False),
    )


def _folder_metadata(drive: Any, folder_id: str) -> dict[str, Any]:
    item = drive.files().get(
        fileId=folder_id,
        fields="id,name,mimeType",
        supportsAllDrives=True,
    ).execute()
    if item.get("mimeType") != FOLDER_MIME:
        raise RuntimeError("Configured Drive reference must be a folder")
    return item


def _list_docs(drive: Any, folder_id: str) -> list[dict[str, Any]]:
    _folder_metadata(drive, folder_id)
    queue = [folder_id]
    seen_folders = {folder_id}
    docs: list[dict[str, Any]] = []
    while queue and len(docs) < MAX_DOCS_SCANNED:
        current = queue.pop(0)
        page_token = None
        while True:
            response = drive.files().list(
                q=(
                    f"'{current}' in parents and trashed = false and "
                    f"(mimeType = '{DOC_MIME}' or mimeType = '{FOLDER_MIME}')"
                ),
                spaces="drive",
                fields="nextPageToken,files(id,name,mimeType,modifiedTime)",
                pageSize=100,
                pageToken=page_token,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            ).execute()
            for item in response.get("files", []):
                if item.get("mimeType") == FOLDER_MIME:
                    child = item["id"]
                    if child not in seen_folders and len(seen_folders) < MAX_FOLDERS:
                        seen_folders.add(child)
                        queue.append(child)
                elif item.get("mimeType") == DOC_MIME:
                    docs.append(item)
                    if len(docs) >= MAX_DOCS_SCANNED:
                        break
            page_token = response.get("nextPageToken")
            if not page_token or len(docs) >= MAX_DOCS_SCANNED:
                break
    return docs


def _extract_text(docs_service: Any, document_id: str) -> str:
    document = docs_service.documents().get(documentId=document_id).execute()
    parts: list[str] = []

    def read(elements: list[dict[str, Any]]) -> None:
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
                        read(cell.get("content", []))

    read(document.get("body", {}).get("content", []))
    return "\n".join(parts)


def sanitize_private_context(text: str) -> str:
    value = text
    for pattern, replacement in SENSITIVE_REPLACEMENTS:
        value = pattern.sub(replacement, value)
    value = re.sub(r"https?://drive\.google\.com/\S+", "[Drive link omitted]", value)
    value = re.sub(r"https?://docs\.google\.com/\S+", "[Drive link omitted]", value)
    value = re.sub(r"\b1[A-Za-z0-9_-]{20,}\b", "[Drive identifier omitted]", value)
    return value.strip()


def _tokens(text: str) -> set[str]:
    stop = {"について", "ため", "こと", "もの", "これ", "それ", "記事", "情報", "更新", "クリニック"}
    return {token.lower() for token in TOKEN_RE.findall(text) if token.lower() not in stop}


def _rank_documents(items: list[dict[str, Any]], query: str, role: str) -> list[dict[str, Any]]:
    query_tokens = _tokens(query)

    def score(item: dict[str, Any]) -> tuple[int, str]:
        name = str(item.get("name", ""))
        overlap = len(query_tokens & _tokens(name))
        role_bonus = 0
        if role == "lhub_archive" and "lhub" in name.lower():
            role_bonus = 3
        if role == "internal_operations" and PRIVATE_NAME_HINTS.search(name):
            role_bonus = 1
        return overlap * 10 + role_bonus, str(item.get("modifiedTime", ""))

    return sorted(items, key=score, reverse=True)[:MAX_SELECTED_PER_SOURCE]


def _load_folder_context(drive: Any, docs_service: Any, folder_id: str, query: str, role: str) -> list[str]:
    if not folder_id.strip():
        return []
    items = _list_docs(drive, folder_id)
    selected = _rank_documents(items, query, role)
    snippets: list[str] = []
    for item in selected:
        raw = _extract_text(docs_service, item["id"])
        safe = sanitize_private_context(raw)[:MAX_CHARS_PER_DOC]
        if safe:
            snippets.append(safe)
    return snippets


def load_reference_context(query: str) -> dict[str, Any]:
    """Return private editorial context without identifiers or source metadata.

    Missing folder variables intentionally return an empty context so local/CI runs remain safe.
    """

    internal_folder = os.getenv("GOOGLE_DRIVE_INTERNAL_REFERENCE_FOLDER_ID", "").strip()
    lhub_folder = os.getenv("GOOGLE_DRIVE_LHUB_ARCHIVE_FOLDER_ID", "").strip()
    raw_credentials = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if not raw_credentials or (not internal_folder and not lhub_folder):
        return {"internal_operations": [], "lhub_archive": [], "available": False}

    drive, docs_service = _services(raw_credentials)
    return {
        "internal_operations": _load_folder_context(
            drive, docs_service, internal_folder, query, "internal_operations"
        ) if internal_folder else [],
        "lhub_archive": _load_folder_context(
            drive, docs_service, lhub_folder, query, "lhub_archive"
        ) if lhub_folder else [],
        "available": True,
    }
