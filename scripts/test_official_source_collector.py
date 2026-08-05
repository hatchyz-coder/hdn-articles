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
    EncodingError,
    READ_TIMEOUT_SECONDS,
    OfficialSourceCollector,
    decode_response_text,
    filter_duplicates,
    generate_fingerprint,
    keyword_score,
    load_sources,
    normalize_url,
    parse_feed,
    parse_html,
    run_collection,
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


def make_response(body: bytes, content_type: str = "text/html", apparent_encoding: str | None = None) -> requests.Response:
    response = requests.Response()
    response.status_code = 200
    response.url = "https://www.mhlw.go.jp/"
    response._content = body
    response.headers["Content-Type"] = content_type
    if apparent_encoding is not None:
        response.encoding = apparent_encoding
    return response


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


def test_utf8_html_decoding() -> None:
    html = '<html><a href="/news/">医療広告ガイドライン</a></html>'
    response = make_response(html.encode("utf-8"), "text/html; charset=utf-8")
    assert "医療広告" in decode_response_text(response)


def test_shift_jis_html_decoding() -> None:
    html = '<html><a href="/news/">医療広告ガイドライン</a></html>'
    response = make_response(html.encode("shift_jis"), "text/html; charset=Shift_JIS")
    assert "医療広告" in decode_response_text(response)


def test_cp932_html_decoding() -> None:
    html = '<html><a href="/news/">医療広告①ガイドライン</a></html>'
    response = make_response(html.encode("cp932"), "text/html; charset=CP932")
    assert "医療広告1ガイドライン" in decode_response_text(response)


def test_unspecified_charset_html_decoding() -> None:
    html = '<html><a href="/news/">再生医療ガイドライン</a></html>'
    response = make_response(html.encode("utf-8"), "text/html", apparent_encoding="ISO-8859-1")
    assert "再生医療" in decode_response_text(response)


def test_meta_charset_html_decoding() -> None:
    html = '<html><head><meta charset="Shift_JIS"></head><a href="/news/">医療広告</a></html>'
    response = make_response(html.encode("shift_jis"), "text/html")
    assert "医療広告" in decode_response_text(response)


def test_mojibake_detection_decodes_with_fallback() -> None:
    html = '<html><a href="/news/">医療広告ガイドライン</a></html>'
    response = make_response(html.encode("utf-8"), "text/html; charset=Shift_JIS")
    assert "医療広告" in decode_response_text(response)


def test_unusable_mojibake_title_is_not_candidate() -> None:
    html = '<a href="/news/">縺薙ｌ縺ｯ譁ｰ逕ｰ医療広告</a>'
    assert parse_html(html, "https://www.mhlw.go.jp/", source()) == []


def test_encoding_error_aggregation() -> None:
    bad = b"\x80\x81\x82\x83\x84\x85"
    response = make_response(bad, "text/html; charset=utf-8")
    with patch("collect_official_sources.decode_candidates", return_value=["utf-8"]):
        try:
            decode_response_text(response)
        except EncodingError:
            pass
        else:
            raise AssertionError("invalid body did not raise EncodingError")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        config_path = tmp_path / "official-sources.yaml"
        config_path.write_text(yaml.safe_dump({"sources": [source()]}, allow_unicode=True), encoding="utf-8")
        args = type(
            "Args",
            (),
            {
                "config": str(config_path),
                "state_path": str(tmp_path / "state.json"),
                "latest_run_path": str(tmp_path / "latest-run.json"),
                "candidates_path": str(tmp_path / "candidates.json"),
                "source_id": "",
                "dry_run": True,
            },
        )()
        with patch.object(OfficialSourceCollector, "collect_source", side_effect=EncodingError("bad encoding")):
            _, latest_run, _, metrics = run_collection(args)
    assert latest_run["source_status_counts"]["encoding_error"] == 1
    assert metrics.encoding_error_sources == 1


def test_source_status_counts_are_consistent() -> None:
    sources = [source(), {**source(), "id": "empty", "name": "Empty"}]
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        config_path = tmp_path / "official-sources.yaml"
        config_path.write_text(yaml.safe_dump({"sources": sources}, allow_unicode=True), encoding="utf-8")
        args = type(
            "Args",
            (),
            {
                "config": str(config_path),
                "state_path": str(tmp_path / "state.json"),
                "latest_run_path": str(tmp_path / "latest-run.json"),
                "candidates_path": str(tmp_path / "candidates.json"),
                "source_id": "",
                "dry_run": True,
            },
        )()
        items = [parse_html('<a href="/news/">医療広告ガイドライン</a>', "https://www.mhlw.go.jp/", source())[0]]
        with patch.object(OfficialSourceCollector, "collect_source", side_effect=[items, []]):
            _, latest_run, _, metrics = run_collection(args)
    counts = latest_run["source_status_counts"]
    assert counts["success"] == 1
    assert counts["no_candidates"] == 1
    assert sum(counts.values()) == metrics.targeted_sources


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
        test_utf8_html_decoding,
        test_shift_jis_html_decoding,
        test_cp932_html_decoding,
        test_unspecified_charset_html_decoding,
        test_meta_charset_html_decoding,
        test_mojibake_detection_decodes_with_fallback,
        test_unusable_mojibake_title_is_not_candidate,
        test_encoding_error_aggregation,
        test_source_status_counts_are_consistent,
    ]
    started = time.monotonic()
    for test in tests:
        test()
    print(json.dumps({"tests": len(tests), "status": "passed", "seconds": round(time.monotonic() - started, 3)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
