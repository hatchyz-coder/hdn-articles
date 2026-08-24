#!/usr/bin/env python3
"""Build HDN official-source opportunity scores without conflating urgency and article value."""
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
    return json.loads(CANDIDATES.read_text(encoding="utf-8")).get("candidates", [])


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
        {"id": i, "title": c.get("title", ""), "source": c.get("source", c.get("source_name", "")), "url": c.get("url", ""), "collector_score": c.get("ai_score", c.get("score", 0)), "published_at": c.get("published_at", ""), "matched_keywords": c.get("matched_keywords", []), "reason": c.get("reason", "")}
        for i, c in enumerate(candidates[:40])
    ]
    prompt = (
        "あなたはHDN Japanの編集長です。対象はクリニック経営者・医療事業者です。"
        "重要: 『速報価値』と『通常記事としての価値』を別々に評価してください。速報性が低い、開催案内、資料公開、統計更新であることだけを理由に捨ててはいけません。"
        "一次情報を入口に、制度の背景、過去比較、統計、海外例、業務への影響、判断基準まで掘れば読み応えのある実務記事になる候補はarticle_value_scoreを高くしてください。"
        "逆に、速報性が高くてもHDN読者の意思決定に結び付かないものはarticle_value_scoreを上げないでください。"
        "JSON配列のみを返し、各要素を {id, article_value_score, urgency_score, authority_score, hdn_fit_score, inquiry_score, total_score, target_segments, article_angle, research_expansion, recommended_cta, recommended_action, rationale} としてください。"
        "各scoreは0〜100。total_scoreは記事価値35%、HDN適合25%、一次情報信頼性20%、問い合わせ価値10%、緊急性10%を目安にしてください。"
        "recommended_actionはarticle/social-only/monitor/skip。記事として深掘りできる候補は速報でなくてもarticleにしてください。"
        "research_expansionには追加確認すべき統計・過去資料・海外事例・関連制度等を日本語配列で入れてください。recommended_ctaはconsultation/lhub/self-pay/sns。\n\n"
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


def fallback_score(candidate: dict[str, Any], index: int) -> dict[str, Any]:
    base = int(candidate.get("ai_score", candidate.get("score", 0)) or 0)
    authority = min(95, 70 + int(candidate.get("source_priority", candidate.get("priority", 0)) or 0) * 5)
    article_value = max(45, base)
    hdn_fit = base
    inquiry = max(base - 10, 30)
    urgency = 45
    total = round(article_value * .35 + hdn_fit * .25 + authority * .20 + inquiry * .10 + urgency * .10)
    return {
        "id": index,
        "article_value_score": article_value,
        "urgency_score": urgency,
        "authority_score": authority,
        "hdn_fit_score": hdn_fit,
        "inquiry_score": inquiry,
        "total_score": total,
        "target_segments": ["クリニック経営者", "医療事業者"],
        "article_angle": candidate.get("reason", "一次情報から実務への影響を掘り下げる"),
        "research_expansion": ["関連する一次資料", "過去との比較", "実務上の判断ポイント"],
        "recommended_cta": candidate.get("suggested_cta", "consultation"),
        "recommended_action": "article" if article_value >= 55 else "monitor",
        "rationale": candidate.get("reason", ""),
    }


def fallback_scores(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [fallback_score(candidate, i) for i, candidate in enumerate(candidates)]


def apply_generation_failure_penalty(candidate: dict[str, Any], opportunity: dict[str, Any]) -> dict[str, Any]:
    """Keep transiently bad candidates retryable without letting them monopolize ranking."""
    failures = max(0, int(candidate.get("generation_failures", 0) or 0))
    penalty = min(50, failures * 10)
    adjusted = dict(opportunity)
    adjusted["generation_failure_penalty"] = penalty
    adjusted["total_score"] = max(0, int(adjusted.get("total_score", 0) or 0) - penalty)
    return adjusted


def main() -> None:
    candidates = load_candidates()
    try:
        ranked = call_openai(candidates)
    except Exception as exc:
        print(f"WARN opportunity AI ranking failed ({type(exc).__name__}); using deterministic fallback scores")
        ranked = []
    ranked = ranked or fallback_scores(candidates)
    by_id = {int(item["id"]): item for item in ranked if "id" in item}
    opportunities: list[dict[str, Any]] = []
    for i, candidate in enumerate(candidates):
        # OpenAI intentionally evaluates only the first 40 candidates for cost/latency.
        # Any unevaluated candidate remains selectable through deterministic fallback
        # scoring rather than disappearing from the day's canonical queue.
        score = by_id.get(i) or fallback_score(candidate, i)
        adjusted = apply_generation_failure_penalty(candidate, score)
        adjusted.pop("id", None)  # preserve the candidate's stable fingerprint-derived id
        opportunities.append({**candidate, **adjusted})
    opportunities.sort(key=lambda x: (int(x.get("total_score", 0)), int(x.get("article_value_score", 0)), int(x.get("authority_score", 0))), reverse=True)
    now = datetime.now(JST)
    OPPORTUNITIES.parent.mkdir(parents=True, exist_ok=True)
    OPPORTUNITIES.write_text(json.dumps({"generated_at": now.isoformat(), "opportunities": opportunities}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / f"{now.date().isoformat()}.md"
    lines = [f"# HDN Opportunity Report — {now.date().isoformat()}", "", f"生成日時: {now.strftime('%Y-%m-%d %H:%M JST')}", "", "## 本日の優先テーマ", ""]
    if not opportunities:
        lines.extend(["候補キューが空です。Collector、pending queue、情報源の到達性を確認してください。", ""])
    else:
        for index, item in enumerate(opportunities[:10], start=1):
            targets = "、".join(item.get("target_segments", []))
            expansion = "、".join(item.get("research_expansion", []))
            lines.extend([f"### {index}. {item.get('title', 'Untitled')}", "", f"- 総合スコア: **{item.get('total_score', 0)}/100**", f"- 通常記事価値: {item.get('article_value_score', 0)}", f"- 速報価値: {item.get('urgency_score', 0)}", f"- 一次情報信頼性: {item.get('authority_score', 0)}", f"- HDN適合度: {item.get('hdn_fit_score', 0)}", f"- 生成失敗ペナルティ: -{item.get('generation_failure_penalty', 0)}", f"- 推奨アクション: {item.get('recommended_action', 'monitor')}", f"- 想定対象: {targets or '未設定'}", f"- 記事角度: {item.get('article_angle', '')}", f"- 追加調査: {expansion or '未設定'}", f"- 出典: {item.get('url', '')}", ""])
    lines.extend(["## 運用メモ", "", "- 速報価値と通常記事価値は別判定です。", "- 候補点数は入口の優先順位であり、公開可否は最終生成記事の品質ゲートで判断します。", "- 生成失敗候補は永久除外せず、失敗回数に応じて優先順位だけ下げます。", "- AI評価対象外の候補もdeterministic fallbackで当日の選択キューに残します。", "- 公開済みURLだけpending queueから除外します。", ""])
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OPPORTUNITIES.relative_to(ROOT)}")
    print(f"Wrote {report_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
