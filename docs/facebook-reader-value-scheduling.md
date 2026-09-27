# Facebook reader-value selection and scheduling

`scripts/select_facebook_candidates.py` scans every published Japanese article. It does not fill a posting quota. A candidate must have a standalone Facebook derivative, at least two cited URLs, concrete examples, reader utility, an HDN/Hatch perspective, and sufficient article depth. Valuable articles with missing or weak derivatives are rewritten before selection instead of being permanently discarded.

`data/facebook-editorial-plan.json` is the reviewed queue. It targets roughly four Facebook posts per week at 19:30 JST, never schedules two on the same day, and mixes editorial, medical-operation, compliance, LHub, and marketing themes. Quality gates override the volume target. The generated `data/facebook-post-ledger.json` distinguishes canonical publication, candidate selection, Metricool scheduling, and verified Facebook publication. Provider acceptance is only `scheduled`; a Facebook provider URL with published status is required before recording `published`.

Run:

```bash
python3 scripts/select_facebook_candidates.py
```

Metricool credentials are never stored in this repository. Evidence returned by Metricool is reduced to non-secret brand/network identifiers, provider post IDs, statuses, timestamps, and public post URLs in `data/facebook-publishing-evidence.json`, then the ledger is rebuilt.

## Channel contract (2026-09-27)

- Facebook: starts with 【日本語タイトル】, 1,200-1,500 characters, canonical article URL, hashtags, standalone value, no quota filler.
- LinkedIn: first line 【日本語 / English】, Japanese section, literal `English follows below.`, naturally reconstructed English section, canonical URL, maximum 3,000 characters, not a Facebook duplicate.
- X: starts with 【タイトル】, one sharp theme, canonical URL, short form, not a Facebook duplicate.

The finalizer validates these mechanical properties. Editorial depth, factual accuracy, legal safety, emotional quality and Hatch perspective still require evidence/editorial review; CI does not claim to verify them automatically.
