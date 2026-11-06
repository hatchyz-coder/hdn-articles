#!/usr/bin/env python3
"""Move a source Google Doc only after published JP/EN pages and both OGPs respond 200."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request

EXPECTED_SOURCE_SHA256 = "377cdda8bba3afb0cbf97915b88d8afb46a313417c07b2885cae8c3b76997bc0"
SITE = "https://article.hdnjapan.com"

def publication_urls(slug: str) -> list[str]:
    if not slug or any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789-" for ch in slug):
        raise ValueError("Unsafe article slug")
    return [f"{SITE}/articles/{slug}/", f"{SITE}/en/articles/{slug}/",
            f"{SITE}/og/ja/{slug}.png", f"{SITE}/og/en/{slug}.png"]

def verify_url(url: str) -> bool:
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "HDN-Archive-Verify/1.0"})
        with urllib.request.urlopen(request, timeout=20) as response:
            if response.status != 200:
                return False
            if url.endswith(".png"):
                return response.headers.get("Content-Type", "").lower().startswith("image/png") and response.read(8) == b"\x89PNG\r\n\x1a\n"
            return bool(response.read(1))
    except (urllib.error.URLError, TimeoutError):
        return False

def archive_file(drive, document_id: str, source: str, archive: str) -> str:
    meta = drive.files().get(fileId=document_id, fields="id,mimeType,parents", supportsAllDrives=True).execute()
    if meta.get("mimeType") != "application/vnd.google-apps.document":
        raise ValueError("Source must be a native Google Doc")
    parents = meta.get("parents") or []
    if archive in parents and source not in parents:
        return "already_archived"
    if source not in parents or archive in parents:
        raise ValueError("Unexpected source parent; refusing move")
    drive.files().update(fileId=document_id, addParents=archive, removeParents=source,
                         fields="id,parents", supportsAllDrives=True).execute()
    new_parents = drive.files().get(fileId=document_id, fields="parents", supportsAllDrives=True).execute().get("parents", [])
    if archive not in new_parents or source in new_parents:
        raise RuntimeError("Archive move could not be verified")
    return "archived"

def main() -> int:
    parser = argparse.ArgumentParser()
    for name in ("slug", "file-id", "source-folder", "archive-folder"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    if hashlib.sha256(args.source_folder.encode()).hexdigest() != EXPECTED_SOURCE_SHA256:
        raise SystemExit("Unapproved Drive source folder")
    if args.archive_folder == args.source_folder:
        raise SystemExit("Archive cannot equal source")
    if not args.file_id:
        print("SKIP: reserve article does not have a Drive source")
        return 0
    urls = publication_urls(args.slug)
    if any(not verify_url(url) for url in urls):
        raise SystemExit("Publication verification incomplete; keep source in place")
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not raw:
        raise SystemExit("Missing service-account credentials")
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    cred = service_account.Credentials.from_service_account_info(
        json.loads(raw), scopes=["https://www.googleapis.com/auth/drive"]
    )
    drive = build("drive", "v3", credentials=cred, cache_discovery=False)
    outcome = archive_file(drive, args.file_id, args.source_folder, args.archive_folder)
    print("Drive archival outcome:", outcome, "slug:", args.slug)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
