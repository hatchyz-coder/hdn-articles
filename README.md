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

## Required GitHub configuration

Before running the content generator, add the following repository secret:

1. Open `Settings`.
2. Open `Secrets and variables` → `Actions`.
3. Create a repository secret named `OPENAI_API_KEY`.
4. Paste the OpenAI project API key as the value.

Optional repository variable:

- `OPENAI_MODEL`: defaults to `gpt-5-mini` when not configured.

## Generate an article draft

1. Open `Actions`.
2. Select `Generate article draft`.
3. Select `Run workflow`.
4. Enter the source URL.
5. Enter a lowercase slug such as `clinic-line-booking`.
6. Select the category and CTA.
7. Run the workflow.

The workflow performs the following steps:

1. Downloads and extracts the source page.
2. Generates a Japanese SEO article draft.
3. Generates X, Facebook, and LinkedIn drafts.
4. Generates an English editorial draft.
5. Runs the Astro production build.
6. Creates a new branch and pull request.

The generated article remains `draft: true`. Review the source accuracy, legal and advertising risks, title, description, internal links, and CTA before changing it to `draft: false` and merging.

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
