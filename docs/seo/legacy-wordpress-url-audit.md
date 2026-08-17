# Legacy WordPress URL audit

Updated: 2026-08-18 JST

## Purpose

Classify legacy `article.hdnjapan.com/YYYY/MM/DD/.../` WordPress URLs still visible in Google so that Search Console exclusions are handled intentionally rather than by trying to eliminate every 404.

## Decision rules

1. **Equivalent current article exists** → preserve intent and consolidate to the current canonical article. Prefer a real HTTP redirect if the hosting layer supports it. Do not create a misleading redirect to a merely related page.
2. **Useful subject but no equivalent current article** → consider a verified rewrite as a new current article; do not automatically resurrect outdated claims.
3. **Outside the current HDN editorial scope / obsolete** → leave removed. A genuine 404/410 is preferable to redirecting unrelated content to the home page.
4. **Regulatory/news content** → never copy forward only to preserve SEO. Re-verify the underlying primary sources and current legal/regulatory status before republishing.

## Initial inventory found in Google

### A. Current-business relevance: review for consolidation or verified rewrite

| Legacy item | Legacy date | Classification | Action |
|---|---:|---|---|
| ROOTS株式会社との協業を開始しました（自費診療クリニック向けデジタル運用支援） | 2025-12-09 | High relevance to LHub / private-care support | Check against the current `roots-lhub-self-pay-partnership` content. If materially equivalent, consolidate to that canonical route. |
| 薬機法・景表法 週刊アップデート（2025-10-27〜11-2） | 2025-10-31 | Historical regulatory/news commentary | Do not redirect to a generic compliance article. Keep removed unless a current article truly supersedes the same subject; verify primary sources before reuse. |
| 薬機法・景表法 週刊アップデート（2025-11-3〜11-9） | 2025-11-10 | Historical regulatory/news commentary | Same rule: historical record only; no automatic migration. |
| 薬機法・景表法 週刊アップデート（2025-11-18〜11-24） | 2025-11-25 | Historical regulatory/news commentary | Same rule. Claims about law effective dates/requirements must be rechecked before any rewrite. |
| 薬機法・景表法 週刊アップデート（2025-11-25〜12-1） | 2025-12-08 | Historical regulatory/news commentary | Same rule. |
| 薬機法・景表法 週刊アップデート（2025-12-2〜12-8） | 2025-12-09 | Historical regulatory/news commentary | Same rule. |
| 薬機法・景表法 週刊アップデート（2025-12-9〜12-15） | 2025-12-21 | Historical regulatory/news commentary | Same rule. |

### B. Outside the current HDN editorial strategy: intentionally retire

The following indexed 2021 WordPress articles are entertainment/media topics and do not fit the current HDN focus on clinic management, private care, patient journeys, medical marketing/compliance and healthcare AI. They should not be redirected to unrelated current pages merely to suppress 404s.

- インターネット・エンターテインメントの増加によるコンテンツの質の低下は止められるのか？芸能タレントのYouTube参入が流れを変える！
- 「遠距離旅行」から「マイクロツーリズム」へ！旅行・観光業の新しい世界が見えてきた
- ミュージシャンのライブ配信はどのくらい儲かる？費用ほぼゼロでイケる近未来のエンタメとは
- 一夜にして興行収入10億越えのキャラクターマーケティングを徹底解明
- 芸能事務所ってどう設立する？意外と礼節に厳しい芸能業界での生き方
- 売れなくてもOK！テレビに出なくても細々と続けるネットタレントの給料はどれくらい？
- 番組制作にかかる費用はいくら？今からメディアに参入することはできるのか
- エンターテイメント業界の仕事がしたい？そこでどんな仕事があるかをチェックしてみた！

Recommended status: **retired / genuine not-found**. Do not add these URLs to the current sitemap and do not point them to the home page.

## Search Console interpretation

- `Not found (404)` is not itself a defect when a page was intentionally removed and has no equivalent replacement.
- `Duplicate / Google chose different canonical` must be investigated only for URLs intended to be indexed.
- `Excluded by noindex` and `Blocked by robots.txt` require action only when the affected URL is meant to be public/indexable.
- Current canonical URLs, internal links and sitemap URLs should all agree.

## Next audit pass

- Export or inspect the exact Search Console URL examples for each exclusion reason.
- Match each legacy high-value URL against current JP/EN article slugs.
- Confirm current target page returns 200 and self-canonicalizes before creating any migration path.
- Maintain a mapping table with status: `redirect`, `retired`, `rewrite-after-verification`, `needs-review`.
- Do not submit broad indexing requests until sitemap/canonical/robots changes are deployed and stable.
