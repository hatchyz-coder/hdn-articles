# Facebook reader-value selection and scheduling

`scripts/select_facebook_candidates.py` scans every published Japanese article. It does not fill a posting quota. A candidate must have a standalone Facebook derivative, at least two cited URLs, concrete examples, reader utility, an HDN/Hatch perspective, and sufficient article depth. Valuable articles with missing or weak derivatives are rewritten before selection instead of being permanently discarded.

`data/facebook-editorial-plan.json` is the reviewed queue. It keeps at least 48 hours between posts and mixes editorial, medical-operation, compliance, and marketing themes. The generated `data/facebook-post-ledger.json` distinguishes canonical publication, candidate selection, Metricool scheduling, and verified Facebook publication. Provider acceptance is only `scheduled`; a Facebook provider URL with published status is required before recording `published`.

Run:

```bash
python3 scripts/select_facebook_candidates.py
```

Metricool credentials are never stored in this repository. Evidence returned by Metricool is reduced to non-secret brand/network identifiers, provider post IDs, statuses, timestamps, and public post URLs in `data/facebook-publishing-evidence.json`, then the ledger is rebuilt.
