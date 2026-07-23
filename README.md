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
- Google Drive 00_KnowledgeBase article candidate reader

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

For Google Drive Knowledge Base Reader, add the following configuration:

1. Share the `00_KnowledgeBase` Google Drive folder with the Google Cloud service account email as viewer.
2. Create a repository secret named `GOOGLE_SERVICE_ACCOUNT_JSON`.
3. Paste the full service account JSON key as the secret value.
4. Create a repository variable named `GOOGLE_DRIVE_KNOWLEDGE_FOLDER_ID`.
5. Set the variable to the folder ID for `00_KnowledgeBase`.

The service account is used with read-only Google Drive and Google Docs scopes. Do not grant edit access to the folder.

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

## Generate a draft from Google Drive Knowledge Base

The `Google Drive Knowledge Base Article PR` workflow can be run manually from the Actions screen.

What it does:

- Recursively scans the configured `00_KnowledgeBase` folder.
- Processes Google Docs only.
- Reads each document name, file ID, URL, updated time, and body text.
- Skips documents already processed at the same updated time.
- Skips source documents already used in existing articles or open pull requests.
- Skips documents with confidentiality concerns and records the reason in the run log.
- Uses AI to score article suitability and E-E-A-T: Experience, Expertise, Authority, and Trust.
- Generates at most one article per run.
- Creates a Draft Pull Request only. It never publishes and never commits directly to `main`.

Generated files include:

- Japanese article draft in `src/content/articles/`
- English editorial draft in `outputs/en/`
- Facebook, LinkedIn, and X drafts in `social/<slug>/`
- Processing state in `data/knowledge-base/processed-docs.json`
- Latest run summary in `data/knowledge-base/latest-run.json`

The PR body includes the source Google Docs URL and updated time. Human review is required before changing `draft: true` to `draft: false`.

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
