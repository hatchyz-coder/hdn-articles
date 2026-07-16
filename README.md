# HDN Articles

HDN Japan Knowledge Base & SEO Article Platform.

## Current architecture

- Astro static site
- Markdown content collection
- GitHub Actions deployment
- RSS generation
- Sitemap generation
- Article structured data
- Shared CTA to HDN, LHub, or private-care support
- URL-based AI article draft generation
- Automatic social copy and English draft generation
- Automatic official-source discovery and AI ranking
- Automatic top-candidate article pull requests

## Staging URL

The initial deployment target is:

`https://hatchyz-coder.github.io/hdn-articles/`

The existing WordPress site at `article.hdnjapan.com` remains unchanged until the new platform is reviewed and approved.

## Content location

Articles are stored in:

`src/content/articles/`

Each article requires frontmatter for title, description, publication date, category, tags, author, draft status, source URL, and CTA type.

Generated social drafts are stored in:

`social/<slug>/`

English editorial drafts are stored in:

`outputs/en/`

Discovered and ranked source candidates are stored in:

`data/candidates/latest.json`

## Required GitHub configuration

Before running the content generator, add the following repository secret:

1. Open `Settings`.
2. Open `Secrets and variables` → `Actions`.
3. Create a repository secret named `OPENAI_API_KEY`.
4. Paste the OpenAI project API key as the value.

Optional repository variable:

- `OPENAI_MODEL`: defaults to `gpt-5-mini` when not configured.

## Generate an article draft from a URL

1. Open `Actions`.
2. Select `Generate article draft`.
3. Select `Run workflow`.
4. Enter the source URL.
5. Enter a lowercase slug such as `clinic-line-booking`.
6. Select the category and CTA.
7. Run the workflow.

The workflow downloads the source, generates the Japanese article, creates social and English drafts, validates the Astro build, and opens a pull request.

## Fully automated discovery and drafting

The automated flow uses two scheduled workflows.

1. `Discover article candidates`
   - Runs on weekday mornings in Japan.
   - Checks configured official sources such as MHLW, PMDA, and the Consumer Affairs Agency.
   - Removes previously seen URLs.
   - Uses AI to score relevance, search intent, business impact, recommended category, CTA, and SEO slug.
   - Saves the ranked queue to `data/candidates/latest.json`.

2. `Auto-generate top article candidate`
   - Runs after the discovery window on weekdays.
   - Selects only candidates scoring 70 or higher.
   - Excludes PDFs, already published source URLs, and source URLs already used by open pull requests.
   - Generates only one article per run.
   - Builds the site and opens a review pull request.
   - Never publishes the article automatically.

Manual end-to-end test:

1. Run `Discover article candidates` from the Actions screen.
2. Confirm that `data/candidates/latest.json` was updated.
3. Run `Auto-generate top article candidate`.
4. Review the automatically created pull request.

The generated article remains `draft: true`. Review source accuracy, legal and advertising risks, title, description, headings, internal links, CTA, and social copy before changing it to `draft: false`.

## Local commands

```bash
npm install
pip install -r requirements.txt
npm run dev
npm run build
```

Manual generator example:

```bash
OPENAI_API_KEY=your_key python scripts/generate_content.py \
  --url "https://example.com/source" \
  --slug "example-article" \
  --category "医療経営" \
  --cta consultation
```

## Publishing flow

1. Generate or edit an article in a pull request.
2. Review facts, wording, SEO, links, and CTA.
3. Change `draft: true` to `draft: false`.
4. Merge the pull request into `main`.
5. GitHub Actions validates and deploys the site.
6. RSS and sitemap are regenerated automatically.

## Domain policy

Recommended final URL: `https://article.hdnjapan.com/`

The subdomain remains appropriate because it is a dedicated publishing platform with its own update cycle. SEO authority is reinforced through strong internal links between the article platform and `hdnjapan.com`.

Do not change DNS or add a production `CNAME` until staging verification is complete.
