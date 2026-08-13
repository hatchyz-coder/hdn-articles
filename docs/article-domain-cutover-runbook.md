# article.hdnjapan.com Cutover Runbook

## Current state

- Production reader URL: `https://article.hdnjapan.com/`
- GitHub Pages source: GitHub Actions workflow
- Current Pages custom domain (`cname`): `article.hdnjapan.com`
- HTTPS enforcement: enabled
- TLS certificate: approved
- DNS: `article CNAME hatchyz-coder.github.io`
- Published Astro article expected on production: `【無難な動画では、患者は動かない】`

## Preconditions

Before changing DNS or the GitHub Pages custom domain, confirm all of the following:

1. Latest `Deploy HDN Articles` workflow is green.
2. The deploy job's `Smoke test deployed site` step is green.
3. `https://hatchyz-coder.github.io/hdn-articles/` loads successfully.
4. The first published article is visible from the staging index.
5. `https://hatchyz-coder.github.io/hdn-articles/sitemap-index.xml` returns successfully.
6. Legacy WordPress DNS/hosting settings are recorded so rollback is possible.
7. TTL for the existing `article.hdnjapan.com` DNS record is reduced in advance where practical.

## Production build target

The deployment workflow derives the Astro build target from the GitHub Pages `base_url` returned by `actions/configure-pages`.

Expected production result:

- `PUBLIC_SITE_URL=https://article.hdnjapan.com`
- `BASE_PATH=/`
- canonical URLs use `https://article.hdnjapan.com/`
- sitemap URLs use the production domain
- site assets and internal routes are built for root `/`

## GitHub Pages custom domain

Configured custom domain:

```text
article.hdnjapan.com
```

## DNS cutover

Production DNS:

```text
article CNAME hatchyz-coder.github.io
```

The legacy Lolipop homepage assignment for `article.hdnjapan.com` is disabled.

## Cutover execution log

```text
Cutover date: 2026-08-13 JST
Operator: hatchyz-coder / HDN
Old hosting: Lolipop WordPress
New DNS record/type/value: article / CNAME / hatchyz-coder.github.io
GitHub Pages DNS check: successful
TLS certificate: approved
Enforce HTTPS: enabled
Final production rebuild: triggered after cutover to rebuild for root custom-domain base URL
```

## Post-cutover checks

Run immediately after the production rebuild:

```text
https://article.hdnjapan.com/
https://article.hdnjapan.com/sitemap-index.xml
```

Confirm:

1. HTTPS is valid with no certificate warning.
2. Home page returns 200.
3. `【無難な動画では、患者は動かない】` appears on the article index.
4. The article detail page loads and does not have broken CSS/assets.
5. Internal links to `hdnjapan.com/medical-sns.html`, `hdnjapan.com/lhub.html`, and the 羽田野剛士 profile resolve correctly.
6. Sitemap returns 200 and contains production-domain URLs.
7. Canonical URL on the article page is `article.hdnjapan.com`, not the GitHub staging hostname.
8. Mobile layout has no horizontal overflow or overlapping text.

## Search / feed checks

After the production domain is stable:

1. Submit or refresh `https://article.hdnjapan.com/sitemap-index.xml` in Google Search Console.
2. Confirm robots directives do not block indexing.
3. Confirm RSS/feed URLs, if used by downstream SNS automation, resolve on the production domain.
4. Keep the GitHub Pages staging hostname out of promotional links once production is live.
5. Expect legacy WordPress URLs to remain temporarily visible in search-engine indexes until recrawled or redirected.

## Rollback trigger

Rollback immediately if any of the following persists after a short propagation allowance:

- homepage or article pages return 4xx/5xx
- HTTPS certificate cannot be established
- CSS/assets fail because of base-path mismatch
- canonical/sitemap URLs point to the wrong host
- article pages cannot be reached from the index

## Rollback procedure

1. Restore the previous DNS record/hosting assignment for `article.hdnjapan.com`.
2. Remove or suspend the GitHub Pages custom domain only if it interferes with returning traffic to WordPress.
3. Re-run the Pages deployment and smoke test after any fix.

## Safe publication order

- First published article: `【無難な動画では、患者は動かない】`
- Keep Article 2 and Article 3 as `draft: true` until the production domain has passed the checks above.
- After stable cutover, publish Article 2, verify, then Article 3 rather than changing all three at once.
