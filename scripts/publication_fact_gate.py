#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse

NUMERIC_RE = re.compile(
    r'(?<![0-9A-Za-z_])(?:\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*'
    r'(?:%|％|倍|円|万円|億円|か月|ヶ月|カ月|M\b|million\b)',
    re.I,
)
CASE_RE = re.compile(
    r'(?:導入後|成功事例|事例|利用企業|施設|宿|民泊|シェアスペース|'
    r'case study|customer|property|inn|guesthouse|facility).{0,100}'
    r'(?:\d+(?:\.\d+)?\s*(?:%|％|倍)|向上|増加|改善|increase|improv|rise|grew|growth)',
    re.I,
)
FEATURE_RE = re.compile(
    r'(LINE(?:公式アカウント)?|LHub|PayPay).{0,90}'
    r'(?:API|継続課金|サブスク|自動決済|決済|連携|接続|できる|可能|'
    r'integrat|connect|recurring|subscription|automatic payment|supports?|enables?|can\b)',
    re.I,
)
FUTURE_END_RE = re.compile(
    r'(?:'
    r'(?:LINE\s*Pay).{0,100}(?:終了に備|終了を見越|今後.{0,20}終了|終了予定|移行予定|'
    r'will\s+(?:cease|end|terminate)|planned\s+termination|upcoming\s+termination)'
    r'|'
    r'(?:prepare\s+for|ahead\s+of).{0,60}(?:LINE\s*Pay).{0,30}(?:shutdown|termination)?'
    r')',
    re.I,
)
INLINE_URL_RE = re.compile(r'https?://[^\s)\]>]+')
MD_LINK_RE = re.compile(r'\[[^\]]+\]\((https?://[^)]+)\)')
OPAQUE_TOOL_CITATION_RE = re.compile(r'【\d+†L\d+(?:-L?\d+)?】')

OFFICIAL_DOMAINS = {
    'linebiz.com',
    'lycorp.co.jp',
    'paypay.ne.jp',
    'hdnjapan.com',
    'l-hub.info',
    'stat.go.jp',
    'mlit.go.jp',
    'mhlw.go.jp',
    'pmda.go.jp',
    'caa.go.jp',
    'ppc.go.jp',
}

@dataclass
class Finding:
    kind: str
    claim: str
    reason: str


def _body(markdown: str) -> str:
    if markdown.startswith('---'):
        parts = markdown.split('---', 2)
        if len(parts) == 3:
            return parts[2]
    return markdown


def _published_at(markdown: str) -> date:
    match = re.search(r'^publishedAt:\s*(\d{4}-\d{2}-\d{2})\s*$', markdown, re.M)
    return datetime.strptime(match.group(1), '%Y-%m-%d').date() if match else date.today()


def _references(markdown: str) -> list[str]:
    return sorted(set(MD_LINK_RE.findall(markdown) + INLINE_URL_RE.findall(markdown)))


def _host(url: str) -> str:
    host = (urlparse(url).hostname or '').lower()
    return host[4:] if host.startswith('www.') else host


def _is_official(url: str) -> bool:
    host = _host(url)
    return any(host == domain or host.endswith('.' + domain) for domain in OFFICIAL_DOMAINS)


def _sentences(text: str) -> list[str]:
    # Keep each Markdown table row intact so evidence can live in the same cell/row.
    return [segment.strip() for segment in re.split(r'(?<=[。！？!?])\s+|\n+', text) if segment.strip()]


def _inline_urls(sentence: str) -> list[str]:
    return INLINE_URL_RE.findall(sentence) + MD_LINK_RE.findall(sentence)


def evaluate(markdown: str) -> dict:
    body = _body(markdown)
    references = _references(markdown)
    findings: list[Finding] = []
    published = _published_at(markdown)

    for sentence in _sentences(body):
        urls = _inline_urls(sentence)
        has_inline_evidence = bool(urls)

        if OPAQUE_TOOL_CITATION_RE.search(sentence):
            findings.append(Finding(
                'opaque_tool_citation', sentence[:240],
                'internal browser/tool citation marker is not a public evidence URL',
            ))

        if NUMERIC_RE.search(sentence) and not has_inline_evidence:
            findings.append(Finding(
                'unsupported_numeric_claim', sentence[:240],
                'numeric/outcome claim has no public evidence URL in the same sentence or table row',
            ))

        if CASE_RE.search(sentence) and not has_inline_evidence:
            findings.append(Finding(
                'unsupported_case_claim', sentence[:240],
                'case/outcome claim has no public evidence URL in the same sentence or table row',
            ))

        if FEATURE_RE.search(sentence) and not any(_is_official(url) for url in urls):
            findings.append(Finding(
                'unverified_product_feature', sentence[:240],
                'LINE/LHub/PayPay capability claim lacks an official inline source',
            ))

        # LINE Pay in Japan ended on 2025-04-30. After that date, future-tense shutdown
        # guidance is stale unless the sentence explicitly describes a historical plan.
        if FUTURE_END_RE.search(sentence) and published > date(2025, 4, 30):
            findings.append(Finding(
                'stale_future_tense', sentence[:240],
                'LINE Pay Japan shutdown is already in the past for this publication date',
            ))

    unique: list[Finding] = []
    seen: set[tuple[str, str]] = set()
    for finding in findings:
        key = (finding.kind, finding.claim)
        if key not in seen:
            unique.append(finding)
            seen.add(key)

    return {
        'publication_fact_gate': not unique,
        'reason': 'ok' if not unique else unique[0].kind,
        'findings': [asdict(finding) for finding in unique],
        'reference_count': len(references),
        'official_reference_count': sum(_is_official(url) for url in references),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--article-path', required=True, type=Path)
    parser.add_argument('--report-path', type=Path)
    args = parser.parse_args()

    result = evaluate(args.article_path.read_text(encoding='utf-8'))
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    print(payload)
    if args.report_path:
        args.report_path.write_text(payload + '\n', encoding='utf-8')
    return 0 if result['publication_fact_gate'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
