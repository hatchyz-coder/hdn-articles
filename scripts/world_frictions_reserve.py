#!/usr/bin/env python3
"""Provider-independent World Frictions reserve materializer.

Reserve specs contain only evergreen editorial framing and a preselected source set.
No model call is used on the fallback path. The final JP/EN/social bundle is built
deterministically, revalidated against current published World Frictions articles,
and then handed back to the existing publication workflow.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import generate_world_frictions as core

ROOT = Path(__file__).resolve().parents[1]
RESERVE_DIR = ROOT / "fallback" / "world-frictions"
WARNING_THRESHOLD = 5
CRITICAL_THRESHOLD = 2


def _spec_paths() -> list[Path]:
    return sorted(RESERVE_DIR.glob("*.json"))


def _load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path.name}: reserve must be an object")
    return data


def _sources(spec: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "title": str(item["title"]).strip(),
            "url": str(item["url"]).strip(),
            "kind": str(item["kind"]).strip(),
        }
        for item in spec["sources"]
    ]


def _jp_body(spec: dict[str, Any]) -> str:
    topic = spec["topic"]
    tension = spec["tension"]
    question = spec["question"]
    practice = spec["practice"]
    lens = spec["lens"]
    return f"""## 違和感は、便利さの反対側にある

{topic}をめぐる議論では、便利さ・効率・安全性のどれか一つだけを見ると、設計の副作用が見えにくくなります。今回の違和感は「{tension}」という構造です。仕組み自体に悪意がなくても、負担の置き場所が偏ると、利用者や現場の誰かが見えない調整役になります。

## 問題は機能ではなく、負担の配分

デジタル施策では、追加された機能や自動化の数が成果として見えやすい一方、確認、例外対応、再入力、説明、問い合わせといった小さな作業は指標からこぼれがちです。ここで見るべきなのは「できるようになったこと」だけではなく、「誰が新しく何をしなければならなくなったか」です。

{question}。この問いを置くだけで、導入側と利用側の評価が同じとは限らないことが見えてきます。制度や技術の正しさと、現場での使いやすさは別の軸です。両方を同時に見る必要があります。

## 一次資料が示すのは、単純な賛否ではない

このreserveは、公開時点で再検索しなければ成立しない速報ではなく、長期的に参照できる一次資料・研究を土台にしています。各資料は、リスク、利用者体験、透明性、説明可能性、アクセシビリティ、監督など、異なる観点から設計上の条件を示しています。

重要なのは、資料を「導入すべき／やめるべき」という二択の根拠に使わないことです。むしろ、どこに人の判断を残すのか、どこで説明を追加するのか、どの利用者が取り残される可能性があるのかを確認するチェックリストとして読む方が実務的です。

## 「平均的な利用者」だけで設計しない

多くの仕組みは標準ケースでは滑らかに動きます。問題は、環境が違う人、途中で条件が変わった人、説明を追加で必要とする人、端末や認証手段に制約がある人など、例外に近い利用者です。

例外を「少数だから後回し」にすると、その少数が問い合わせ窓口や現場スタッフへ集中します。結果として、システム上は効率化していても、人の側では調整作業が増えることがあります。効率化の成否は、標準ケースの速度だけでは測れません。

## 自動化の外側に、人の仕事が残る

自動化すると人の仕事が消える、という説明は分かりやすいですが、実際には仕事の形が変わることがあります。入力、確認、監視、例外処理、説明、訂正といった役割が別の場所へ移動するからです。

そのため、導入前には「何を自動化するか」と同時に「自動化できなかった時に誰が受けるか」を決める必要があります。ここを決めずに導入すると、最終的な責任だけが人に戻り、判断材料はシステム側に残るという不均衡が起こります。

## 実務で見るべき四つの点

第一に、利用者が次に何をすべきか分かるか。第二に、例外時の出口があるか。第三に、判断理由を必要な範囲で説明できるか。第四に、仕組みの失敗を人が修正できるか。この四点は、製品名や業界が変わっても使える確認軸です。

{practice}。大きな刷新より、問い合わせが集中している一工程、説明が繰り返されている一画面、判断が止まる一箇所から直す方が、負担の変化を観察しやすくなります。

## KPIだけでは見えないものを拾う

処理件数、時間、コストなどの指標は重要です。ただし、それだけでは「利用者が理解できたか」「担当者が例外対応に追われていないか」「同じ説明を何度もしていないか」は分かりません。

そこで、定量指標に加えて、戻り操作、問い合わせ理由、手作業の補正、担当者間の引き継ぎなどを観察します。数字が改善していても、見えない作業が増えているなら、単純に成功とは言えません。

## 導入前と導入後を同じ物差しで見る

新しい仕組みを評価する時は、導入後の速さだけを見るのではなく、導入前に誰が何をしていたかを残しておくことも重要です。作業が減った場所と、新しく増えた確認や説明を同じ表に並べれば、「効率化」の中で負担が移動しただけなのか、本当に全体が軽くなったのかを判断しやすくなります。

また、問題が起きた時だけ人の対応へ戻る設計では、その人が必要な文脈を持っているかも確認します。普段は自動化されているほど、例外時に必要な情報が見えにくくなることがあります。通常時と例外時を別々の仕組みにせず、同じ運用として設計する視点が欠かせません。

## 構造として見る

このテーマを「新技術への抵抗」や「利用者の慣れ不足」で終わらせると、改善機会を失います。{lens}。設計者、運営者、利用者、現場スタッフのそれぞれが、別のコストを負担しています。

違和感を拾う意味は、誰かを責めることではありません。仕組みの目的と、実際に発生している負担の間にズレがないかを見ることです。目的が正しくても、負担の配分が不公平なら、設計は見直せます。

## 最後に

便利さは、画面の速さや機能数だけでは決まりません。説明を読まなくても進めること、例外時に戻れること、人に相談できること、自分がなぜその判断を受けたのか理解できることも含まれます。

「便利になった」という言葉の裏で、誰の作業が増えたのか。誰が判断を引き受けたのか。誰が例外として扱われたのか。そこまで見ると、デジタル化や自動化を賛成・反対の二択ではなく、より良い設計の問題として考えられます。"""


def _en_body(spec: dict[str, Any]) -> str:
    topic = spec["topic_en"]
    tension = spec["tension_en"]
    question = spec["question_en"]
    practice = spec["practice_en"]
    lens = spec["lens_en"]
    return f"""## Friction often sits on the other side of convenience

Debates about {topic} are easy to reduce to speed, convenience, safety, or efficiency. The structural tension here is that {tension}. A system does not need malicious intent to create a lopsided burden. If one group absorbs the extra checking, correction, explanation, or exception handling, the cost has merely moved.

## The real question is where the work goes

New functions and automated steps are visible. Small compensating tasks are not. Re-entry, verification, escalation, explanation, monitoring, and manual correction often disappear from headline metrics.

{question} That question separates technical capability from operational experience. A system can be valid in principle and still create avoidable friction in practice.

## Primary sources are better used as design constraints

This reserve is deliberately evergreen. It relies on primary or research material that can remain useful beyond a single news cycle. The sources address risk, user experience, transparency, accessibility, oversight, or accountability from different angles.

They should not be read as a binary instruction to adopt or reject a technology. A more useful interpretation is to treat them as design constraints: where should human judgment remain, what needs to be explained, who may be excluded, and what happens when the standard path fails?

## Do not design only for the average case

Most systems look smooth when the user has the expected device, documentation, ability, language, timing, and context. Friction becomes visible at the edges: interrupted processes, accessibility needs, unusual circumstances, missing credentials, or cases that require explanation.

If edge cases are dismissed as rare, they often reappear as concentrated support work. The system may look efficient while people outside the system perform the hidden reconciliation.

## Automation changes work more often than it removes work

Automation can reduce repetitive tasks, but it can also relocate them. Verification, exception handling, monitoring, appeals, corrections, and reassurance may still require people.

That is why an implementation plan should define not only what will be automated, but also who owns the failure path. Without that decision, responsibility can return to a person after the relevant context has been hidden inside the system.

## Four practical checks

First, can the user understand the next action? Second, is there an escape route for exceptions? Third, can a consequential decision be explained at the right level? Fourth, can a person correct the system when it is wrong?

{practice} Small, observable changes are easier to evaluate than a broad transformation whose hidden costs appear only after launch.

## Measure the work that metrics miss

Throughput, time, and cost matter, but they do not fully capture repeated questions, manual reconciliation, abandoned steps, or handoff failures. Those signals are operational evidence too.

A process can improve on a dashboard while creating more invisible work elsewhere. Good evaluation therefore combines quantitative performance with observations of where people stop, return, escalate, or compensate.

## Look at the structure, not only the tool

{lens} Designers, operators, users, and frontline staff can each experience a different version of the same system.

The point of identifying friction is not to blame a particular actor. It is to compare the stated purpose of a system with the burden it actually distributes. If the purpose is sound but the burden is misplaced, the design can still be improved.

## Closing question

Convenience is not just speed or feature count. It also includes understandability, reversibility, access to a human path, and the ability to understand or contest important outcomes.

When a system becomes more convenient, whose work disappeared and whose work increased? Who now carries the exceptions? Asking those questions turns a vague discomfort into a practical design problem."""


def _facebook(spec: dict[str, Any], url: str) -> str:
    base = f"""【{spec['title']}】

「便利になった」と言われる仕組みほど、少しだけ別の角度から見たくなります。

今回の違和感は、{spec['tension']}という構造です。

新しい機能や自動化は目に見えます。一方で、確認、再入力、例外対応、問い合わせ、説明、手作業での補正は成果指標からこぼれやすい。つまり、仕事が消えたのではなく、見えにくい場所へ移動しただけかもしれません。

そこで重要なのは「何ができるようになったか」だけでなく、「誰が新しく何をしなければならなくなったか」を見ることです。

{spec['question']}

標準ケースだけなら滑らかでも、端末、認証、言語、アクセシビリティ、途中変更などの条件が少し違うだけで、人のサポートが必要になることがあります。その出口を最初から設計しているかどうかで、現場負担は大きく変わります。

自動化についても同じです。定型作業が減っても、監視、訂正、説明、例外判断が残るなら、その仕事を誰が引き受けるのかを決めなければなりません。

実務では、利用者が次の行動を理解できるか、例外時に戻れるか、必要な説明ができるか、人が誤りを修正できるか。この四つを見るだけでも、多くの摩擦を拾えます。

{spec['practice']}

派手な改革より、一つの問い合わせ、一つの手戻り、一つの説明の重複を減らす。その積み重ねの方が、仕組みが本当に便利になったかを確認しやすいと思います。

便利さの裏側で、誰の作業が増えたのか。

そこを見ないまま「DX」「AI」「自動化」という言葉だけを進めると、効率化したはずなのに人が疲れるという逆転が起こります。

世界中の違和感は、こういう小さな負担の移動に隠れているのかもしれません。

{url}

#世界の違和感 #業務設計 #デジタル"""
    return base


def _candidate(spec: dict[str, Any]) -> dict[str, Any]:
    sources = _sources(spec)
    url = f"https://article.hdnjapan.com/articles/{spec['slug']}/"
    canonical = {
        "title": spec["title"],
        "social_title": spec["social_title"],
        "description": spec["description"],
        "category": "世界の違和感",
        "tags": spec["tags"],
        "content_type": "opinion",
        "summary": spec["summary"],
        "body_markdown": _jp_body(spec),
        "sources": sources,
    }
    english = {
        "title": spec["title_en"],
        "social_title": spec["social_title_en"],
        "description": spec["description_en"],
        "category": "World Frictions",
        "tags": spec["tags_en"],
        "content_type": "opinion",
        "summary": spec["summary_en"],
        "body_markdown": _en_body(spec),
        "sources": sources,
    }
    return {
        "publish": True,
        "slug": spec["slug"],
        "selection_reason": "provider-independent validated reserve",
        "canonical": canonical,
        "english_canonical": english,
        "note": f"{canonical['title']}\n\n{canonical['summary']}\n\n{canonical['body_markdown']}\n\n{url}",
        "linkedin_newsletter": f"{canonical['title']}\n\n{canonical['summary']}\n\n{spec['lens']}\n\n{url}",
        "linkedin_post": f"{canonical['title']}\n\n{canonical['summary']}\n\nEnglish follows below.\n\n{english['summary']}\n\n{url}\n\n#WorldFrictions #DigitalDesign",
        "facebook": _facebook(spec, url),
        "x": f"{canonical['title']}\n{spec['summary']}\n{url}\n#世界の違和感",
        "reposts": [
            f"便利さの裏で誰の作業が増えたのか。{spec['question']}",
            f"{spec['tension']}――仕組みの目的と負担の配分を分けて考える。",
            f"自動化の評価は『消えた作業』だけでなく『移動した作業』まで見る。",
        ],
    }


def validate_spec(spec: dict[str, Any], *, check_duplicate: bool = True) -> tuple[dict[str, Any], list[dict[str, str]]]:
    required = {
        "slug","title","social_title","description","summary","tags",
        "title_en","social_title_en","description_en","summary_en","tags_en",
        "topic","tension","question","practice","lens",
        "topic_en","tension_en","question_en","practice_en","lens_en","sources",
    }
    missing = sorted(required - set(spec))
    if missing:
        raise ValueError("missing reserve fields: " + ", ".join(missing))
    candidate = _candidate(spec)
    sources, _ = core.validate_sources(candidate["canonical"]["sources"], set())
    if check_duplicate:
        core.check_duplicate(candidate, core.existing_world_frictions(), sources)
    core.validate_candidate(
        candidate,
        existing=core.existing_world_frictions() if check_duplicate else [],
        retrieved=set(),
    )
    return candidate, sources


def unused_specs() -> list[tuple[Path, dict[str, Any]]]:
    rows = []
    for path in _spec_paths():
        spec = _load(path)
        if (core.ARTICLE_DIR / f"{spec.get('slug','')}.md").exists():
            continue
        rows.append((path, spec))
    return rows


def reserve_health(remaining: int) -> str:
    if remaining <= CRITICAL_THRESHOLD:
        return "critical"
    if remaining <= WARNING_THRESHOLD:
        return "warning"
    return "healthy"


def materialize_reserve(provider_reason: str) -> dict[str, Any]:
    errors: list[str] = []
    for path, spec in unused_specs():
        try:
            candidate, sources = validate_spec(spec, check_duplicate=True)
            canonical_url, _written = core.write_bundle(candidate, sources)
            remaining = len(unused_specs())
            result = {
                "publish": True,
                "slug": spec["slug"],
                "title": spec["title"],
                "canonical_url": canonical_url,
                "reason": "validated_reserve_after_provider_failure",
                "reserve_remaining": remaining,
                "reserve_health": reserve_health(remaining),
                "provider_failure": provider_reason,
            }
            core.write_github_output(**result)
            core.write_summary([
                "## World Frictions validated reserve",
                "",
                f"- Slug: {spec['slug']}",
                f"- Provider trigger: {provider_reason}",
                f"- Reserve remaining: {remaining}",
                f"- Reserve health: {reserve_health(remaining)}",
            ])
            print(json.dumps(result, ensure_ascii=False))
            return result
        except Exception as exc:
            errors.append(f"{path.name}: {exc}")
    core.write_github_output(
        publish="false",
        reason="world_frictions_reserve_exhausted",
        reserve_remaining=0,
        reserve_health="critical",
    )
    raise RuntimeError("No valid World Frictions reserve remains: " + " | ".join(errors))


def main() -> int:
    rows = unused_specs()
    for path, spec in rows:
        validate_spec(spec, check_duplicate=False)
        print(path.name)
    print(json.dumps({
        "reserve_total": len(_spec_paths()),
        "reserve_unused": len(rows),
        "reserve_health": reserve_health(len(rows)),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
