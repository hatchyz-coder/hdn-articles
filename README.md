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

The `Google Drive Knowledge Base Article PR` workflow runs on weekdays and can also be run manually from the Actions screen. It is optimized for daily generation of one candidate article, not for re-reading the entire Knowledge Base.

What it does:

- Uses change detection and the `knowledge-base-state` branch cache instead of recursively scanning the configured `00_KnowledgeBase` folder.
- On the first run, seeds from only the 20 most recently updated Google Docs found in the cached `00_KnowledgeBase` folder set.
- On later runs, uses the Google Drive Changes API and cached document metadata to avoid API access for unchanged documents.
- Processes Google Docs only.
- Reads document name, file ID, URL, and updated time before any document body access.
- Immediately skips processed document IDs.
- Skips source documents already used in existing articles or open pull requests.
- Evaluates meeting notes, including documents under `01_MeetingNotes`, as normal article candidates unless concrete sensitive content is present.
- Skips documents with concrete confidentiality concerns and records the reason in the run log. The heuristic targets personal information, patient identifiers, contract amounts, credentials, explicit confidentiality markers, and non-public customer names; it does not skip a document merely because it contains words such as meeting note or sales discussion.
- Sends only the first 5,000 characters of each unprocessed candidate document for preview scoring.
- Uses AI to score at most two documents for article suitability and E-E-A-T: Experience, Expertise, Authority, and Trust.
- Prepares official-source follow-up fields for human review: additional verification topics, official information source candidates, and claims not supported by the source document alone.
- Fetches the full Google Docs body only for the final selected article candidate.
- For long selected documents, sends only beginning, middle, and ending chunks to the final article-generation request instead of issuing multiple chunk-summary calls.
- Generates at most one article per run.
- Creates a Draft Pull Request only. It never publishes and never commits directly to `main`.
- Sets an 8-minute workflow timeout, stops remaining script work after five minutes, and targets 60 seconds for no-candidate runs and 180 seconds for candidate runs.

Generated files include:

- Japanese article draft in `src/content/articles/`
- English editorial draft in `outputs/en/`
- Facebook, LinkedIn, and X drafts in `social/<slug>/`
- Processing state in `data/knowledge-base/processed-docs.json` on the dedicated `knowledge-base-state` branch
- Latest run summary in `data/knowledge-base/latest-run.json` on the dedicated `knowledge-base-state` branch

Processing state is restored from and saved back to the `knowledge-base-state` branch on every workflow run, including runs that produce no article candidate. The workflow also uploads the state directory as a GitHub Actions artifact named `knowledge-base-state-<run_id>` with 30-day retention. This keeps processing state out of `main` while preserving skip logs, zero-candidate runs, processed file IDs, updated times, and the latest research-review notes.

The workflow summary reports Drive取得件数, 新規件数, AI評価件数, 記事生成件数, API呼び出し回数, 入力文字数, OpenAI処理時間, Drive処理時間, GitHub処理時間, ファイルI/O時間, キャッシュ処理時間, and 総実行時間. Logs include start, finish, and second-level timings for Drive, OpenAI, GitHub, file I/O, cache, preview export, preview AI evaluation, full document fetch, and article generation.

The source reader is organized around source MIME types so future support can add Google Drive PDFs, Word documents, PowerPoint files, Excel workbooks, Markdown, and text files without changing the workflow contract. Those sources are defined but disabled until extractor and safety handling are implemented. Official-source enrichment is also isolated behind the research-extension output so later implementations can check MHLW, PMDA, Consumer Affairs Agency, academic societies, government agencies, manufacturer official pages, and papers before final article drafting.

The PR body includes the source Google Docs URL, updated time, E-E-A-T score, and official-source review preparation. Human review is required before changing `draft: true` to `draft: false`.

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
