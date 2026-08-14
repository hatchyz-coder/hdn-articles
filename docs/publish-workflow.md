# Article approval-to-publish flow

Article generation remains review-first. Generated articles must stay `draft: true` until an authorized reviewer explicitly approves publication.

## Flow

1. The automation discovers and ranks a public primary source.
2. It generates an article draft plus social and English drafts in a pull request.
3. Editorial review verifies source accuracy, HDN relevance, private Drive redaction, and unsupported claims.
4. If publication is approved, an authorized repository collaborator comments exactly `/publish` on the article pull request.
5. `Publish approved article` then:
   - verifies the PR targets `main` and comes from this repository;
   - requires exactly one changed article with `draft: true`;
   - changes it to `draft: false` and updates `publishedAt` to the JST publication date;
   - runs lint, typecheck, tests, build, and migration check;
   - commits the publication flag and merges the PR;
   - lets the normal GitHub Pages deployment workflow publish and smoke-test the site.

## Safety guardrails

- Comments from external contributors cannot trigger publishing.
- Fork pull requests cannot be auto-published.
- A PR changing zero or multiple article files is rejected.
- An article that is already public cannot be republished through this trigger.
- Drive source identifiers and private reference content are never required for the publish step.
- If validation fails, the PR remains open and unpublished.
