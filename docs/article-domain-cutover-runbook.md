# article.hdnjapan.com Cutover Runbook

## Current state

- Existing production reader URL: `https://article.hdnjapan.com/` (legacy WordPress)
- New Astro staging URL: `https://hatchyz-coder.github.io/hdn-articles/`
- GitHub Pages source: GitHub Actions workflow
- Current Pages custom domain (`cname`): none
- HTTPS enforcement: enabled
- Staging deployment smoke test: passing
- Published Astro article currently expected on staging: `【無難な動画では、患者は動かない】`

## Preconditions

Before changing DNS or the GitHub Pages custom domain, confirm all of the following:

1. Latest `Deploy HDN Articles` workflow is green.
2. The deploy job's `Smoke test deployed site` step is green.
3. `https://hatchyz-coder.github.io/hdn-articles/` loads successfully.
4. The first published article is visible from the staging index.
5. `https://hatchyz-coder.github.io/hdn-articles/sitemap-index.xml` returns successfully.
6. Legacy WordPress DNS/hosting settings are recorded so rollback is possible.
7. TTL for the existing `article.hdnjapan.com` DNS record is reduced in advance where practical.

## Production variables

Set repository variables before the production rebuild:

```text
ARTICLES_SITE_URL=https://article.hdnjapan.com
ARTICLES_BASE_PATH=/
```

Expected result:

- canonical URLs use `https://article.hdnjapan.com/`
- sitemap URLs use the production domain
- site assets and internal routes are built for root `/`

## GitHub Pages custom domain

Configure the repository's GitHub Pages custom domain as:

```text
article.hdnjapan.com
```

Do not remove the legacy WordPress hosting first. Keep it available until the new domain is verified.

## DNS cutover

For a subdomain, point `article.hdnjapan.com` to the GitHub Pages hostname used by this repository/account according to the DNS provider's supported record type and GitHub Pages requirements.

Before saving the DNS change, capture the old DNS record value in the change log below.

### Change log

```text
Cutover time:
Operator:
Old DNS record/type/value:
New DNS record/type/value:
Old TTL:
New TTL:
```

## Post-cutover checks

Run immediately after DNS begins resolving to the new site:

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

## Rollback trigger

Rollback immediately if any of the following persists after a short propagation allowance:

- homepage or article pages return 4xx/5xx
- HTTPS certificate cannot be established
- CSS/assets fail because of base-path mismatch
- canonical/sitemap URLs point to the wrong host
- article pages cannot be reached from the index

## Rollback procedure

1. Restore the previous DNS record for `article.hdnjapan.com`.
2. Keep the new Astro deployment available at `https://hatchyz-coder.github.io/hdn-articles/` for diagnosis.
3. Restore repository variables to staging values if necessary:

```text
ARTICLES_SITE_URL=https://hatchyz-coder.github.io
ARTICLES_BASE_PATH=/hdn-articles
```

4. Remove or suspend the GitHub Pages custom domain only if it interferes with returning traffic to WordPress.
5. Re-run the Pages deployment and staging smoke test after any fix.

## Safe publication order

- First published article: `【無難な動画では、患者は動かない】`
- Keep Article 2 and Article 3 as `draft: true` until the production domain has passed the checks above.
- After stable cutover, publish Article 2, verify, then Article 3 rather than changing all three at once.
