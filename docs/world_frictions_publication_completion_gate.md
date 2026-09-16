# World Frictions Publication Completion Gate

## Purpose

Prevent a generated, committed, deployed, scheduled, or pending item from being reported as published before the requested destination is verifiably live.

## Non-negotiable state model

These states are distinct and must never be collapsed:

1. GENERATED — copy/assets exist.
2. CANONICAL_COMMITTED — JP/EN article pair is committed.
3. CANONICAL_LIVE — production deploy succeeded and live JP/EN URLs pass smoke tests.
4. SOCIAL_SCHEDULED — provider accepted a future post; PENDING is not published.
5. SOCIAL_LIVE — destination network confirms the post is live, or a supported post-publication retrieval returns the published item.

Only states 3 and 5 may be described as "published" for their respective destinations.

## Five mandatory verification passes

Before a World Frictions job may be reported complete, run all five checks in order. A failure stops completion and triggers remediation; never substitute inference.

### Pass 1 — Artifact completeness

Verify canonical JP and EN files, required metadata, sources, social derivative files, canonical links, no prohibited asterisk emphasis, and Facebook copy target length 1,200–1,500 Japanese characters unless an explicit editorial exception is recorded.

### Pass 2 — Canonical production verification

Require successful build and deployment. Smoke-test the live JP canonical URL, EN pair, World Frictions index, and JP/EN OGP assets. A merge to main is not publication.

### Pass 3 — Social submission verification

For each requested social destination, verify the provider accepted the post, auto-publish is enabled when intended, destination network is correct, content is the final approved derivative, and the returned provider state/id is persisted. PENDING means scheduled only.

### Pass 4 — Post-publication verification

After the scheduled time, verify the destination post itself through a supported provider/network retrieval or other direct evidence. Absence from the scheduler is not evidence of publication. Never say "probably published", "processing", or equivalent as a completion claim.

### Pass 5 — End-to-end reconciliation

Reconcile canonical URL, article slug/title, destination, provider post ID, scheduled time, actual publication evidence, and duplicate status. Only after this pass may the run emit COMPLETED.

## Completion vocabulary

Allowed:
- "生成済み" only after Pass 1.
- "本番記事公開済み" only after Pass 2.
- "Facebook予約済み / PENDING" only after Pass 3.
- "Facebook公開済み" only after Pass 4 and Pass 5.

Forbidden before evidence:
- "投稿完了"
- "公開済み"
- "公開処理に回った可能性"
- any inference from disappearance from a scheduling list.

## Failure behavior

If a provider cannot expose post-publication evidence, report the strongest verified state only. Do not downgrade the verification requirement by guessing. Preserve the provider post ID and surface the verification gap as an unresolved gate.

## Facebook-specific contract

Facebook derivatives should normally be 1,200–1,500 Japanese characters, begin with a Japanese title in 【】, use ですます調, contain the canonical clean URL, and work as a standalone digest. Before submission, count characters deterministically. After submission, persist the Metricool/provider ID and state. After the publication time, verify the live destination; PENDING is never completion.

## Incident regression cases

The following must all be rejected as incomplete:

1. JP article committed but EN pair missing.
2. JP/EN merged but production URL returns 404.
3. Facebook post accepted with status PENDING.
4. Facebook item disappears from scheduled-post list after its due time but no published-post evidence exists.
5. Social copy is materially shorter than the configured Facebook editorial target without an explicit exception.

These five regression cases constitute the minimum recurrence test set for changes to the World Frictions publishing pipeline.
