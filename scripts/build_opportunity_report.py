#!/usr/bin/env python3
"""Build HDN opportunity scores and a daily editorial report."""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ROOT / "data" / "candidates" / "latest.json"
OPPORTUNITIES = ROOT / "data" / "opportunities" / "latest.json"
REPORT_DIR = ROOT / "reports" / "daily"

JST = timezone(timedelta(hours=9))


def load_candidates() -> list[dict[str, Any]]:
    if not CANDIDATES.exists():
        return []
    payload = json.loads(CANDIDATES.read_text(encoding="utf-8"))
    return payload.get("candidates", [])


def extract_output_text(data: dict[str, Any]) -> str:
    text = data.get("output_text", "")
    if text:
        return str(text)
    chunks: list[str] = []
    for item in data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                chunks.append(content.get("text", ""))
    return "".join(chunks)


def call_openai(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or not candidates:
        return []

    compact = [
        {
            "id": i,
            "title": c.get("title", ""),
            "source": c.get("source", ""),
            "url": c.get("url", ""),
            "ai_score": c.get("ai_score", 0),
            "reason": c.get("reason", ""),
        }
        for i, c in enumerate(candidates[:20])
    ]

    prompt = (
        "あなたはHDN Japanの編集長兼事業開発責任者です。"
        "クリニック経営者・医療事業者からの問い合わせ獲得を目的に、各候補を評価してください。"
        "HDNの主力は、医療機関向け経営支援、自費診療導入支援、患者導線設計、LHub導入運用です。"
        "JSON配列のみを返し、各要素を "
        "{id, seo_score, inquiry_score, urgency_score, authority_score, hdn_fit_score, total_score, "
        "target_segments, article_angle, recommended_cta, recommended_action, rationale} としてください。"
        "各scoreは0〜100。recommended_ctaはconsultation/lhub/self-payのいずれか。"
        "recommended_actionはarticle/social-only/monitor/skipのいずれか。"
        "target_segmentsは日本語配列。total_scoreはSEO25%、問い合わせ30%、緊急性15%、一次情報信頼性15%、HDN適合度15%を目安にしてください。"
        "単なる告知、採用、調達、人事、検索意図が弱い内容は低評価にしてください。\n\n"
        + json.dumps(compact, ensure_ascii=False)
    )

    response = requests.post(
        "https://api.openai.com/v1/responses",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": os.getenv("OPENAI_MODEL", "gpt-5-mini"), "input": prompt, "store": False},
        timeout=180,
    )
    response.raise_for_status()
    text = extract_output_text(response.json()).strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I | re.S)
    return json.loads(text)


def fallback_scores(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scored = []
    for i, c in enumerate(candidates):
        base = int(c.get("ai_score", 0))
        scored.append({
            "id": i,
            "seo_score": base,
            "inquiry_score": max(base - 5, 0),
            "urgency_score": min(base + 5, 100),
            "authority_score": 85,
            "hdn_fit_score": base,
            "total_score": round(base * 0.7 + 85 * 0.3),
            "target_segments": ["クリニック経営者", "医療事業者"],
            "article_angle": c.get("reason", "実務への影響を整理する"),
            "recommended_cta": c.get("suggested_cta", "consultation"),
            "recommended_action": "article" if base >= 70 else "monitor",
            "rationale": c.get("reason", ""),
        })
    return scored


def main() -> None:
    candidates = load_candidates()
    ranked = call_openai(candidates) or fallback_scores(candidates)
    by_id = {int(item["id"]): item for item in ranked}

    opportunities: list[dict[str, Any]] = []
    for i, candidate in enumerate(candidates):
        score = by_id.get(i)
        if not score:
            continue
        merged = {**candidate, **score}
        opportunities.append(merged)

    opportunities.sort(key=lambda x: int(x.get("total_score", 0)), reverse=True)
    now = datetime.now(JST)
    payload = {"generated_at": now.isoformat(), "opportunities": opportunities}

    OPPORTUNITIES.parent.mkdir(parents=True, exist_ok=True)
    OPPORTUNITIES.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / f"{now.date().isoformat()}.md"
    lines = [
        f"# HDN Opportunity Report — {now.date().isoformat()}",
        "",
        f"生成日時: {now.strftime('%Y-%m-%d %H:%M JST')}",
        "",
        "## 本日の優先テーマ",
        "",
    ]

    if not opportunities:
        lines.extend([
            "本日は記事化基準を満たす候補がありません。",
            "",
            "### 推奨対応",
            "",
            "- 前回候補キューが空か確認する",
            "- 監視ソースのHTML構造変更を確認する",
            "- キーワードまたは情報源を追加する",
        ])
    else:
        for index, item in enumerate(opportunities[:5], start=1):
            targets = "、".join(item.get("target_segments", []))
            lines.extend([
                f"### {index}. {item.get('title', 'Untitled')}",
                "",
                f"- 総合スコア: **{item.get('total_score', 0)}/100**",
                f"- SEO価値: {item.get('seo_score', 0)}",
                f"- 問い合わせ価値: {item.get('inquiry_score', 0)}",
                f"- 緊急性: {item.get('urgency_score', 0)}",
                f"- 一次情報信頼性: {item.get('authority_score', 0)}",
                f"- HDN適合度: {item.get('hdn_fit_score', 0)}",
                f"- 推奨アクション: {item.get('recommended_action', 'monitor')}",
                f"- 想定対象: {targets or '未設定'}",
                f"- 推奨記事角度: {item.get('article_angle', '')}",
                f"- 推奨CTA: {item.get('recommended_cta', 'consultation')}",
                f"- 選定理由: {item.get('rationale', '')}",
                f"- 出典: {item.get('url', '')}",
                "",
            ])

    lines.extend([
        "## 運用メモ",
        "",
        "- 記事化は一次情報の確認後に行います。",
        "- 法務・医療広告上の判断が必要な内容は自動公開しません。",
        "- CTAは記事内容に応じて、HDN相談・自費導入・LHubから選択します。",
        "",
    ])
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OPPORTUNITIES.relative_to(ROOT)}")
    print(f"Wrote {report_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
