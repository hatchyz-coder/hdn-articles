# Legacy WordPress migration inventory

## Final migration policy

The former WordPress archive on `article.hdnjapan.com` is retired by default.

Only content with clear current business value is recreated on the Astro site. Historical PV alone is not a reason to preserve an article; retention requires a concrete contribution to current credibility, conversion, active partnerships, or search demand.

## Decision rules

- **MIGRATE**: Preserve only when the article documents a current, material HDN business asset.
- **RETIRE**: Do not recreate. Allow the old URL to return 404 and fall out of the search index naturally.
- Do not redirect unrelated legacy URLs to the home page.
- Add a real 301/308 only when a genuinely equivalent replacement page exists and a redirect-capable layer is available.

## Migrate — ROOTS partnership only

| Legacy date | Article | Decision | Destination |
|---|---|---|---|
| 2025-12-09 | ROOTS株式会社との協業を開始しました（自費診療クリニック向けデジタル運用支援） | MIGRATE | `/articles/roots-lhub-self-pay-partnership/` |

Reason: this article documents an active partnership and directly supports HDN's current clinic consulting, self-pay care support, and LHub positioning.

## Retire — all other WordPress articles

This includes the 2025 pharmaceutical / advertising compliance weekly updates. They are not migrated or consolidated unless future Search Console, analytics, backlink, lead, or conversion data demonstrates a specific business reason to restore one.

Examples already discovered and retired include:

- 2025 薬機法・景表法 週刊アップデート群
- 2020〜2021 スポーツ、芸能、旅行、VR、模型等の記事群
- Any other former WordPress post not explicitly listed in the ROOTS migration row above

## Search-engine handling

1. Keep the new sitemap limited to live Astro content.
2. Do not add retired WordPress URLs to the sitemap.
3. Let Google recrawl retired paths and observe 404.
4. Do not use blanket redirects from historical URLs to `/`.
5. If the ROOTS legacy URL needs equity preservation, add a path-specific permanent redirect only after a redirect-capable edge layer is introduced.

## Redirect-platform constraint

GitHub Pages does not provide flexible server-side per-path HTTP redirect rules. The site can operate correctly without restoring the old archive; retired paths may remain 404. A redirect-capable edge layer should only be introduced if the ROOTS legacy URL has enough search/backlink value to justify it.

## Implementation order

1. Migrate and publish the ROOTS partnership article.
2. Confirm the new ROOTS article appears in sitemap and production smoke checks.
3. Leave every other former WordPress article retired.
4. Reconsider an individual retired URL only if measurable SEO or conversion data later justifies recovery.
