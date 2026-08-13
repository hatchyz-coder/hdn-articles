# Article automation production flow

## Production source of truth

- Public site: `https://article.hdnjapan.com/`
- Repository: `hatchyz-coder/hdn-articles`
- Content source of truth: `src/content/articles/`
- Generated articles remain `draft: true` until editorial approval.

## Main automated flow

`HDN Growth Pipeline` runs on weekdays at `22:15 UTC` (`07:15 JST` the following day).

1. Discover and rank source candidates.
2. Build the opportunity report.
3. Exclude sources already represented by open pull requests.
4. Select the highest-value candidate above the score threshold.
5. Generate the Japanese article, social drafts, and English draft.
6. Resolve the current GitHub Pages custom-domain target.
7. Build against the production URL/base path.
8. Open a review pull request.

The pipeline does **not** automatically publish AI-generated content. Publication still requires changing `draft: true` to `draft: false` and merging the reviewed change.

## Manual entry points

- `Generate article draft`: create a draft from a specified source URL.
- `Auto Article PR`: select from the current candidate queue and create a draft PR.
- `HDN Growth Pipeline`: full discovery-to-draft pipeline.

All three build against the active GitHub Pages custom domain rather than a hard-coded staging URL.

## Publication guardrails

- Medical, legal, pharmaceutical-advertising, and performance claims require human review.
- Generated drafts must not bypass PR review.
- Duplicate source URLs already represented by open PRs are excluded.
- Sitemap/RSS only include content that is actually published by the Astro site.
- WordPress is no longer a publishing source of truth.

## Operational target

The desired steady state is one high-value draft PR per eligible weekday, not automatic bulk publication. If no candidate meets the threshold, the run should finish without creating an article PR.
