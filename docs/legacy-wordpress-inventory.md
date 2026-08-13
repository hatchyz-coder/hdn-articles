# Legacy WordPress migration inventory

## Purpose

This inventory tracks indexed URLs from the former WordPress site on `article.hdnjapan.com` after the Astro cutover.

The goal is not to preserve the entire historical archive. The goal is to retain content that supports HDN's current business positioning: clinic management support, self-pay care, LHub, medical marketing, and pharmaceutical / advertising compliance.

## Decision rules

- **MIGRATE**: Current-business relevance is high. Recreate as a maintained Astro article or news item.
- **CONSOLIDATE**: Topic remains useful but multiple dated articles should become one current evergreen article.
- **RETIRE**: No meaningful connection to current HDN business. Do not recreate on Astro.
- Old URLs must not be redirected blindly to the home page. Redirect only where a genuinely equivalent replacement exists.

## Priority A — migrate

| Legacy date | Article | Decision | Proposed destination |
|---|---|---|---|
| 2025-12-09 | ROOTS株式会社との協業を開始しました（自費診療クリニック向けデジタル運用支援） | MIGRATE | `/articles/roots-lhub-self-pay-partnership/` |

Reason: directly supports current LHub / clinic consulting credibility and documents an active business partnership.

## Priority B — consolidate into evergreen content

| Legacy date | Article | Decision | Proposed destination |
|---|---|---|---|
| 2025-10-31 | 【2025年10月27日〜11月2日】薬機法・景表法 週刊アップデート | CONSOLIDATE | compliance archive / evergreen regulatory article |
| 2025-11-10 | 【2025年11月3日〜11月9日】薬機法・景表法 週刊アップデート | CONSOLIDATE | compliance archive / evergreen regulatory article |
| 2025-11-25 | 【2025年11月18日〜11月24日】薬機法・景表法 週刊アップデート | CONSOLIDATE | 2025薬機法改正・診療報酬関連の整理記事 |
| 2025-12-08 | 【2025年11月25日〜12月1日】薬機法・景表法 週刊アップデート | CONSOLIDATE | 景表法違反事例・広告管理の整理記事 |
| 2025-12-09 | 【2025年12月2日〜12月8日】薬機法・景表法 週刊アップデート | CONSOLIDATE | 景表法確約手続の整理記事 |
| 2025-12-21 | 【2025年12月9日〜12月15日】薬機法・景表法 週刊アップデート | CONSOLIDATE | 2025年広告規制総括記事 |

Reason: the subject matter fits Avviso / compliance marketing, but weekly snapshots age quickly. Maintaining several stale weekly pages would weaken the new knowledge-base structure. Preserve useful substance in fewer current articles.

## Priority C — retire

The following indexed legacy content is outside the current HDN business scope and should not be recreated.

| Legacy date | Article | Decision |
|---|---|---|
| 2020-07-01 | これからどうなるスポーツ界？無観客でもその臨場感を伝えればニューノーマルな世界が切り開かれる | RETIRE |
| 2020-07-13 | 変わりゆくプロスポーツ！日本におけるスポーツもエンターテイメント化が必至となるその理由とは？ | RETIRE |
| 2020-09-28 | 人気のガンプラや模型を作るプロモデラーになるにはどうしたらいい？ | RETIRE |
| 2020-10-05 | VR(仮想現実)はコロナ禍での新しいエンタメ界の収益源となり得るのか？ | RETIRE |
| 2021-02-27 | 芸能事務所ってどう設立する？ | RETIRE |
| 2021-02-27 | 番組制作にかかる費用はいくら？ | RETIRE |
| 2021-02-27 | エンターテイメント業界の仕事がしたい？ | RETIRE |
| 2021-02-27 | 売れなくてもOK！テレビに出なくても細々と続けるネットタレントの給料はどれくらい？ | RETIRE |
| 2021-02-27 | ミュージシャンのライブ配信はどのくらい儲かる？ | RETIRE |
| 2021-02-28 | インターネット・エンターテインメントの増加によるコンテンツの質の低下は止められるのか？ | RETIRE |
| 2021-02-28 | 「遠距離旅行」から「マイクロツーリズム」へ！ | RETIRE |
| 2021-02-28 | 一夜にして興行収入10億越えのキャラクターマーケティングを徹底解明 | RETIRE |

## Search-engine handling

1. Keep the new sitemap limited to live Astro content.
2. Do not add retired legacy URLs to the sitemap.
3. Allow Google to recrawl retired URLs and observe 404 unless a true replacement exists.
4. Where a migrated/consolidated page is created, map the corresponding legacy URL to the new page using an HTTP redirect layer capable of real 301/308 redirects.
5. Do not use blanket redirects from every historical WordPress URL to `/`; this creates soft-404-like migration signals and poor user relevance.

## Redirect-platform constraint

GitHub Pages does not provide flexible server-side per-path HTTP redirect rules. Before implementing legacy-path redirects, evaluate placing a redirect-capable edge layer in front of GitHub Pages (for example, a DNS/proxy platform with redirect rules) or accept natural 404 removal for retired URLs.

## Next implementation order

1. Migrate the ROOTS partnership article.
2. Create one evergreen compliance article from the strongest 2025 weekly content rather than restoring every weekly page.
3. Build a legacy URL → new URL mapping only for migrated/consolidated pages.
4. Leave unrelated 2020–2021 entertainment archive retired.
5. Continue adding discoveries to this inventory if Search Console exposes additional indexed legacy URLs.

## Inventory limitation

This is a first-pass inventory based on URLs still discoverable through public search indexes after cutover. It is intentionally not treated as a complete export of the former WordPress database. Search Console coverage data and any available WordPress export should be used to expand the list if full historical accounting becomes necessary.
