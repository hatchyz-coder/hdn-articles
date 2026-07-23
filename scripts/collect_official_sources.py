#!/usr/bin/env python3
"""Collect official-source updates without generating article drafts."""

from __future__ import annotations

import argparse
import email.utils
import hashlib
import ipaddress
import json
import re
import socket
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, quote, unquote, urlencode, urljoin, urlparse, urlunparse

import requests
import yaml
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "official-sources.yaml"
DATA_DIR = ROOT / "data" / "official-sources"
STATE_PATH = DATA_DIR / "state.json"
LATEST_RUN_PATH = DATA_DIR / "latest-run.json"
CANDIDATES_PATH = DATA_DIR / "candidates.json"

USER_AGENT = "HDN-OfficialSourceCollector/0.1 (+https://hdnjapan.com/)"
CONNECT_TIMEOUT_SECONDS = 10
READ_TIMEOUT_SECONDS = 20
MAX_RETRIES = 1
MAX_PER_SOURCE = 10
MAX_TOTAL = 50
MAX_REDIRECTS = 3
TITLE_IMPORTANT_TERMS = [
    "医療広告",
    "薬機法",
    "景品表示法",
    "個人情報",
    "再生医療",
    "美容医療",
    "オンライン診療",
    "医療DX",
    "ガイドライン",
    "注意喚起",
    "措置命令",
    "安全性",
    "API",
    "Search",
    "AI",
]


class CollectorError(Exception):
    """Expected per-source collection error."""


class UnsupportedSource(CollectorError):
    """Source appears to require JavaScript or an unsupported format."""


@dataclass
class Metrics:
    targeted_sources: int = 0
    successful_sources: int = 0
    failed_sources: int = 0
    unsupported_sources: int = 0
    fetched_candidates: int = 0
    new_candidates: int = 0
    duplicate_candidates: int = 0
    http_requests: int = 0
    execution_seconds: float = 0.0
    source_results: list[dict[str, Any]] = field(default_factory=list)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_sources(path: Path = CONFIG_PATH) -> list[dict[str, Any]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    sources = data.get("sources", [])
    if not isinstance(sources, list):
        raise ValueError("official-sources.yaml must contain a sources list")
    for source in sources:
        required = ["id", "name", "category", "official_url", "feed_url", "enabled", "priority", "keywords", "allowed_domains"]
        missing = [key for key in required if key not in source]
        if missing:
            raise ValueError(f"source {source.get('id', '<unknown>')} is missing: {', '.join(missing)}")
    return sources


def normalize_domain(domain: str) -> str:
    return domain.strip().lower().lstrip(".").encode("idna").decode("ascii")


def host_is_blocked(host: str) -> bool:
    normalized = host.strip("[]").lower()
    if normalized in {"localhost", "0", "0.0.0.0"} or normalized.endswith(".localhost"):
        return True
    try:
        ip = ipaddress.ip_address(normalized)
    except ValueError:
        return False
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def resolved_host_is_public(host: str) -> bool:
    if host_is_blocked(host):
        return False
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    for info in infos:
        address = info[4][0]
        if host_is_blocked(address):
            return False
    return True


def normalize_url(raw_url: str, base_url: str | None = None) -> str:
    value = (raw_url or "").strip()
    if not value:
        raise ValueError("empty URL")
    parsed = urlparse(urljoin(base_url, value) if base_url else value)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise ValueError(f"unsupported URL scheme: {parsed.scheme}")
    if not parsed.netloc or not parsed.hostname:
        raise ValueError("URL host is required")
    host = parsed.hostname.encode("idna").decode("ascii").lower()
    if host_is_blocked(host):
        raise ValueError("blocked host")
    port = parsed.port
    netloc = host
    if port and not (parsed.scheme.lower() == "https" and port == 443) and not (parsed.scheme.lower() == "http" and port == 80):
        netloc = f"{host}:{port}"
    path = quote(unquote(parsed.path or "/"), safe="/:@")
    query = urlencode(sorted(parse_qsl(parsed.query, keep_blank_values=True)), doseq=True)
    return urlunparse((parsed.scheme.lower(), netloc, path, "", query, ""))


def url_allowed(url: str, allowed_domains: list[str]) -> bool:
    try:
        parsed = urlparse(normalize_url(url))
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    domains = [normalize_domain(domain) for domain in allowed_domains]
    return any(host == domain or host.endswith(f".{domain}") for domain in domains)


def infer_content_type(url: str, content_type_header: str = "") -> str:
    lowered = urlparse(url).path.lower()
    header = content_type_header.lower()
    if lowered.endswith(".pdf") or "application/pdf" in header:
        return "pdf"
    if "xml" in header or lowered.endswith((".rss", ".atom", ".xml")):
        return "feed"
    return "html"


def generate_fingerprint(source_id: str, title: str, url: str) -> str:
    normalized_url = normalize_url(url)
    payload = "\n".join([source_id, normalized_url, re.sub(r"\s+", " ", title).strip().lower()])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def matched_keywords(title: str, keywords: list[str]) -> list[str]:
    lowered = title.lower()
    return [keyword for keyword in keywords if str(keyword).lower() in lowered]


def keyword_score(title: str, keywords: list[str]) -> int:
    return min(30, len(matched_keywords(title, keywords)) * 10)


def score_candidate(candidate: dict[str, Any], now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    priority_score = min(35, max(0, int(candidate.get("priority", 0))) * 7)
    keyword_points = min(30, len(candidate.get("matched_keywords", [])) * 10)
    title_points = min(20, sum(5 for term in TITLE_IMPORTANT_TERMS if term.lower() in candidate.get("title", "").lower()))
    freshness_points = 5
    published_at = candidate.get("published_at")
    if published_at:
        try:
            published = datetime.fromisoformat(str(published_at).replace("Z", "+00:00"))
            age_days = max(0, (now - published).days)
            freshness_points = 15 if age_days <= 7 else 10 if age_days <= 30 else 5 if age_days <= 180 else 0
        except ValueError:
            freshness_points = 5
    return max(0, min(100, priority_score + keyword_points + title_points + freshness_points))


def parse_date(value: str | None) -> str:
    if not value:
        return ""
    text = value.strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat()
    except ValueError:
        pass
    try:
        parsed = email.utils.parsedate_to_datetime(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError):
        return ""


class OfficialSourceCollector:
    def __init__(self, session: requests.Session | None = None) -> None:
        self.session = session or requests.Session()
        self.metrics = Metrics()

    def fetch(self, url: str, allowed_domains: list[str]) -> requests.Response:
        current = normalize_url(url)
        if not url_allowed(current, allowed_domains):
            raise CollectorError(f"URL is outside allowed domains: {current}")
        host = urlparse(current).hostname or ""
        if not resolved_host_is_public(host):
            raise CollectorError(f"URL host is not public: {host}")

        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = self._fetch_once(current, allowed_domains)
                return response
            except (requests.RequestException, CollectorError) as exc:
                last_error = exc
                if attempt >= MAX_RETRIES:
                    break
        raise CollectorError(str(last_error) if last_error else "fetch failed")

    def _fetch_once(self, url: str, allowed_domains: list[str]) -> requests.Response:
        current = url
        for _ in range(MAX_REDIRECTS + 1):
            self.metrics.http_requests += 1
            response = self.session.get(
                current,
                headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/atom+xml, text/html, application/xhtml+xml;q=0.9, */*;q=0.1"},
                timeout=(CONNECT_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS),
                allow_redirects=False,
            )
            if response.is_redirect or response.is_permanent_redirect:
                location = response.headers.get("Location", "")
                current = normalize_url(location, current)
                if not url_allowed(current, allowed_domains):
                    raise CollectorError(f"redirect left allowed domains: {current}")
                host = urlparse(current).hostname or ""
                if not resolved_host_is_public(host):
                    raise CollectorError(f"redirect target host is not public: {host}")
                continue
            response.raise_for_status()
            final_url = normalize_url(response.url or current)
            if not url_allowed(final_url, allowed_domains):
                raise CollectorError(f"final URL is outside allowed domains: {final_url}")
            return response
        raise CollectorError("too many redirects")

    def collect_source(self, source: dict[str, Any]) -> list[dict[str, Any]]:
        allowed_domains = list(source.get("allowed_domains") or [])
        feed_url = (source.get("feed_url") or "").strip()
        target_url = feed_url or source["official_url"]
        response = self.fetch(target_url, allowed_domains)
        content_type = infer_content_type(target_url, response.headers.get("Content-Type", ""))
        response.encoding = response.encoding or response.apparent_encoding
        if feed_url or content_type == "feed":
            raw_items = parse_feed(response.text, response.url or target_url, source)
        else:
            raw_items = parse_html(response.text, response.url or target_url, source)
        if not raw_items and looks_javascript_required(response.text):
            raise UnsupportedSource("JavaScript appears to be required")
        return raw_items[:MAX_PER_SOURCE]


def looks_javascript_required(html: str) -> bool:
    lowered = html.lower()
    markers = ["enable javascript", "javascript is required", "requires javascript", "please enable js"]
    return any(marker in lowered for marker in markers)


def parse_feed(xml_text: str, base_url: str, source: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise CollectorError(f"feed parse failed: {exc}") from exc
    items: list[dict[str, Any]] = []
    nodes = list(root.findall(".//item")) or list(root.findall(".//{http://www.w3.org/2005/Atom}entry")) or list(root.findall(".//entry"))
    for node in nodes:
        title = text_of(node, ["title", "{http://www.w3.org/2005/Atom}title"])
        link = text_of(node, ["link"])
        atom_link = node.find("{http://www.w3.org/2005/Atom}link")
        if atom_link is not None and atom_link.get("href"):
            link = atom_link.get("href", "")
        published = parse_date(text_of(node, ["pubDate", "published", "updated", "{http://www.w3.org/2005/Atom}published", "{http://www.w3.org/2005/Atom}updated"]))
        item = build_candidate(source, title, link, base_url, published)
        if item:
            items.append(item)
    return items


def text_of(node: ET.Element, names: list[str]) -> str:
    for name in names:
        found = node.find(name)
        if found is not None and found.text:
            return re.sub(r"\s+", " ", found.text).strip()
    return ""


def parse_html(html: str, base_url: str, source: dict[str, Any]) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for anchor in soup.select("a[href]"):
        title = re.sub(r"\s+", " ", anchor.get_text(" ", strip=True) or anchor.get("title", "")).strip()
        if len(title) < 4:
            continue
        item = build_candidate(source, title, anchor.get("href", ""), base_url, find_nearby_datetime(anchor))
        if not item or item["url"] in seen:
            continue
        seen.add(item["url"])
        items.append(item)
        if len(items) >= MAX_PER_SOURCE:
            break
    return items


def find_nearby_datetime(anchor: Any) -> str:
    for parent in [anchor.parent, anchor.parent.parent if anchor.parent else None]:
        if not parent:
            continue
        time_node = parent.find("time")
        if time_node:
            parsed = parse_date(time_node.get("datetime") or time_node.get_text(" ", strip=True))
            if parsed:
                return parsed
    return ""


def build_candidate(source: dict[str, Any], title: str, link: str, base_url: str, published_at: str = "") -> dict[str, Any] | None:
    try:
        url = normalize_url(link, base_url)
    except ValueError:
        return None
    if not url_allowed(url, list(source.get("allowed_domains") or [])):
        return None
    title = re.sub(r"\s+", " ", title).strip()
    if not title:
        return None
    keywords = matched_keywords(title, list(source.get("keywords") or []))
    candidate = {
        "source_id": source["id"],
        "source_name": source["name"],
        "category": source["category"],
        "title": title,
        "url": url,
        "published_at": published_at,
        "discovered_at": utc_now(),
        "content_type": infer_content_type(url),
        "matched_keywords": keywords,
        "priority": int(source.get("priority", 0)),
        "status": "new",
        "fingerprint": generate_fingerprint(source["id"], title, url),
    }
    candidate["score"] = score_candidate(candidate)
    return candidate


def seen_sets(state: dict[str, Any], existing_candidates: dict[str, Any]) -> tuple[set[str], set[str]]:
    urls = set(state.get("seen_urls", []))
    fingerprints = set(state.get("seen_fingerprints", []))
    for item in existing_candidates.get("candidates", []):
        if item.get("url"):
            urls.add(item["url"])
        if item.get("fingerprint"):
            fingerprints.add(item["fingerprint"])
    return urls, fingerprints


def filter_duplicates(candidates: list[dict[str, Any]], state: dict[str, Any], existing_candidates: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
    seen_urls, seen_fingerprints = seen_sets(state, existing_candidates)
    run_urls: set[str] = set()
    run_fingerprints: set[str] = set()
    fresh: list[dict[str, Any]] = []
    duplicates = 0
    for item in candidates:
        url = item["url"]
        fingerprint = item["fingerprint"]
        if url in seen_urls or fingerprint in seen_fingerprints or url in run_urls or fingerprint in run_fingerprints:
            duplicates += 1
            continue
        run_urls.add(url)
        run_fingerprints.add(fingerprint)
        fresh.append(item)
    return fresh, duplicates


def update_state(state: dict[str, Any], candidates: list[dict[str, Any]], latest_run: dict[str, Any]) -> dict[str, Any]:
    urls = set(state.get("seen_urls", []))
    fingerprints = set(state.get("seen_fingerprints", []))
    for item in candidates:
        urls.add(item["url"])
        fingerprints.add(item["fingerprint"])
    return {
        "updated_at": utc_now(),
        "seen_urls": sorted(urls),
        "seen_fingerprints": sorted(fingerprints),
        "last_run": latest_run,
    }


def run_collection(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], Metrics]:
    started = time.monotonic()
    sources = [source for source in load_sources(Path(args.config)) if source.get("enabled") is True]
    if args.source_id:
        sources = [source for source in sources if source.get("id") == args.source_id]
    collector = OfficialSourceCollector()
    collector.metrics.targeted_sources = len(sources)

    all_candidates: list[dict[str, Any]] = []
    for source in sources:
        result = {"source_id": source["id"], "source_name": source["name"], "status": "success", "candidate_count": 0, "error": ""}
        try:
            items = collector.collect_source(source)
            result["candidate_count"] = len(items)
            collector.metrics.successful_sources += 1
            collector.metrics.fetched_candidates += len(items)
            all_candidates.extend(items)
        except UnsupportedSource as exc:
            result["status"] = "unsupported"
            result["error"] = str(exc)
            collector.metrics.unsupported_sources += 1
            print(f"UNSUPPORTED {source['id']}: {exc}", flush=True)
        except Exception as exc:
            result["status"] = "failed"
            result["error"] = str(exc)
            collector.metrics.failed_sources += 1
            print(f"WARN {source['id']}: {exc}", flush=True)
        collector.metrics.source_results.append(result)
        if len(all_candidates) >= MAX_TOTAL:
            all_candidates = all_candidates[:MAX_TOTAL]
            break

    all_candidates.sort(key=lambda item: (item.get("score", 0), item.get("priority", 0), item.get("published_at", "")), reverse=True)
    all_candidates = all_candidates[:MAX_TOTAL]
    state = load_json(Path(args.state_path), {"seen_urls": [], "seen_fingerprints": []})
    existing_candidates = load_json(Path(args.candidates_path), {"candidates": []})
    new_candidates, duplicates = filter_duplicates(all_candidates, state, existing_candidates)
    collector.metrics.duplicate_candidates = duplicates
    collector.metrics.new_candidates = len(new_candidates)
    collector.metrics.execution_seconds = round(time.monotonic() - started, 3)

    latest_run = {
        "generated_at": utc_now(),
        "dry_run": bool(args.dry_run),
        "source_id": args.source_id or "",
        "metrics": collector.metrics.__dict__,
        "top_candidates": new_candidates[:5],
    }
    candidates_payload = {
        "generated_at": utc_now(),
        "candidates": new_candidates,
    }
    next_state = update_state(state, new_candidates, latest_run)
    return candidates_payload, latest_run, next_state, collector.metrics


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect official source candidates")
    parser.add_argument("--config", default=str(CONFIG_PATH))
    parser.add_argument("--state-path", default=str(STATE_PATH))
    parser.add_argument("--latest-run-path", default=str(LATEST_RUN_PATH))
    parser.add_argument("--candidates-path", default=str(CANDIDATES_PATH))
    parser.add_argument("--source-id", default="")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    candidates_payload, latest_run, next_state, metrics = run_collection(args)
    write_json(Path(args.candidates_path), candidates_payload)
    write_json(Path(args.latest_run_path), latest_run)
    if not args.dry_run:
        write_json(Path(args.state_path), next_state)
    elif not Path(args.state_path).exists():
        write_json(Path(args.state_path), {"updated_at": utc_now(), "seen_urls": [], "seen_fingerprints": [], "last_run": latest_run})
    print(
        "Official source collection finished: "
        f"sources={metrics.targeted_sources} success={metrics.successful_sources} "
        f"failed={metrics.failed_sources} unsupported={metrics.unsupported_sources} "
        f"new={metrics.new_candidates} duplicates={metrics.duplicate_candidates} "
        f"http={metrics.http_requests} seconds={metrics.execution_seconds}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
