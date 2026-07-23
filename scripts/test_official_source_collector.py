#!/usr/bin/env python3
"""Mock-only tests for the official source collector."""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import requests
import yaml

from collect_official_sources import (
    CONNECT_TIMEOUT_SECONDS,
    READ_TIMEOUT_SECONDS,
    OfficialSourceCollector,
    filter_duplicates,
    generate_fingerprint,
    keyword_score,
    load_sources,
    normalize_url,
    parse_feed,
    parse_html,
    url_allowed,
)


def source() -> dict:
    return {
        "id": "mhlw",
        "name": "厚生労働省",
        "category": "government",
        "official_url": "https://www.mhlw.go.jp/",
        "feed_url": "",
        "enabled": True,
        "priority": 5,
        "keywords": ["医療広告", "再生医療", "ガイドライン"],
        "allowed_domains": ["mhlw.go.jp"],
    }


def test_yaml_loading() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "official-sources.yaml"
        path.write_text(yaml.safe_dump({"sources": [source()]}, allow_unicode=True), encoding="utf-8")
        loaded = load_sources(path)
    assert loaded[0]["id"] == "mhlw"
    assert loaded[0]["enabled"] is True


def test_url_normalization() -> None:
    normalized = normalize_url("HTTPS://WWW.MHLW.GO.JP:443/news/../news/?b=2&a=1#frag")
    assert normalized == "https://www.mhlw.go.jp/news/../news/?a=1&b=2"


def test_allowed_domains() -> None:
    assert url_allowed("https://www.mhlw.go.jp/news/", ["mhlw.go.jp"])
    assert not url_allowed("https://example.com/news/", ["mhlw.go.jp"])


def test_duplicate_detection() -> None:
    item = parse_html('<a href="/news/">医療広告ガイドライン更新</a>', "https://www.mhlw.go.jp/", source())[0]
    fresh, duplicates = filter_duplicates([item], {"seen_urls": [item["url"]], "seen_fingerprints": []}, {"candidates": []})
    assert fresh == []
    assert duplicates == 1


def test_fingerprint_generation() -> None:
    first = generate_fingerprint("mhlw", "医療広告", "https://www.mhlw.go.jp/a?b=1")
    second = generate_fingerprint("mhlw", "医療広告", "https://www.mhlw.go.jp/a?b=1#ignored")
    assert first == second
    assert len(first) == 64


def test_keyword_score() -> None:
    assert keyword_score("再生医療と医療広告ガイドライン", ["再生医療", "医療広告", "関係なし"]) == 20


def test_timeout_tuple_is_used() -> None:
    class FakeSession:
        def __init__(self) -> None:
            self.timeout = None

        def get(self, *args, **kwargs):
            self.timeout = kwargs["timeout"]
            response = requests.Response()
            response.status_code = 200
            response.url = "https://www.mhlw.go.jp/"
            response._content = b"<html></html>"
            response.headers["Content-Type"] = "text/html"
            return response

    fake = FakeSession()
    collector = OfficialSourceCollector(session=fake)  # type: ignore[arg-type]
    with patch("collect_official_sources.resolved_host_is_public", return_value=True):
        collector.fetch("https://www.mhlw.go.jp/", ["mhlw.go.jp"])
    assert fake.timeout == (CONNECT_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS)


def test_invalid_url_rejection() -> None:
    for url in ["file:///etc/passwd", "http://localhost/", "http://127.0.0.1/admin"]:
        try:
            normalize_url(url)
        except ValueError:
            continue
        raise AssertionError(f"invalid URL was accepted: {url}")


def test_feed_parsing() -> None:
    xml = """
    <rss><channel><item>
      <title>医療広告ガイドラインのお知らせ</title>
      <link>https://www.mhlw.go.jp/news/item.html</link>
      <pubDate>Wed, 22 Jul 2026 00:00:00 GMT</pubDate>
    </item></channel></rss>
    """
    items = parse_feed(xml, "https://www.mhlw.go.jp/", source())
    assert len(items) == 1
    assert items[0]["content_type"] == "html"
    assert items[0]["matched_keywords"] == ["医療広告", "ガイドライン"]


def test_html_candidate_extraction() -> None:
    html = """
    <main>
      <article><time datetime="2026-07-22T00:00:00+00:00"></time>
      <a href="/news/doc.pdf">再生医療の安全性ガイドライン</a></article>
      <a href="https://evil.example/">医療広告</a>
    </main>
    """
    items = parse_html(html, "https://www.mhlw.go.jp/", source())
    assert len(items) == 1
    assert items[0]["content_type"] == "pdf"
    assert items[0]["published_at"].startswith("2026-07-22")


def main() -> int:
    tests = [
        test_yaml_loading,
        test_url_normalization,
        test_allowed_domains,
        test_duplicate_detection,
        test_fingerprint_generation,
        test_keyword_score,
        test_timeout_tuple_is_used,
        test_invalid_url_rejection,
        test_feed_parsing,
        test_html_candidate_extraction,
    ]
    started = time.monotonic()
    for test in tests:
        test()
    print(json.dumps({"tests": len(tests), "status": "passed", "seconds": round(time.monotonic() - started, 3)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
