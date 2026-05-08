# RepoRadar

Fully automated content pipeline that discovers trending GitHub repos and standout hackathon projects, evaluates them with an LLM, renders Instagram-native images, and publishes via the Graph API. Zero human in the loop, per the [PRD](prd.md).

```
GitHub Search API   →                                              ┌── Mon repo
                       Velocity scan → LLM evaluation              │
Devpost (Wed)       →                  → Caption gen → Render →    ├── Wed carousel
                                                       Upload →    │
                                                       IG Graph →  └── Fri repo
```

## Setup

### 1. Python

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium    # one-time browser download for the renderer
```

### 2. `.env`

```bash
cp .env.template .env
```

Fill in the keys you have. Minimum to scan + evaluate: `GH_TOKEN` plus one LLM key. The default LLM provider is `openai`.

| Variable | Required for | Where |
|---|---|---|
| `GH_TOKEN` | scanning | github.com → Settings → Developer Settings → PAT (no scopes needed for public repos) |
| `LLM_PROVIDER` | evaluation | `claude`, `gemini`, or `openai` |
| `ANTHROPIC_API_KEY` | `LLM_PROVIDER=claude` | console.anthropic.com |
| `GEMINI_API_KEY` | `LLM_PROVIDER=gemini` | aistudio.google.com |
| `OPENAI_API_KEY` | `LLM_PROVIDER=openai` | platform.openai.com |
| `IG_ACCESS_TOKEN` | publishing | Meta Developer dashboard, long-lived Page token |
| `IG_BUSINESS_ACCOUNT_ID` | publishing | linked IG Business account |
| `IG_APP_ID` / `IG_APP_SECRET` | token refresh | Meta app settings |
| `IMAGE_HOST_*` | publishing | R2 / S3 / B2 — public-read bucket + HTTPS base URL |

### 3. External account checklist (manual, one-time)

These can't be done from code:

- [ ] **Facebook Business** account
- [ ] **Meta Developer** app (developers.facebook.com)
- [ ] Convert IG to **Business / Creator**, link to a Facebook Page
- [ ] Add **Instagram Graph API** product to the app
- [ ] Request `instagram_content_publish` permission (app review — submit early; can take days)
- [ ] Generate a **long-lived Page Access Token** (60-day expiry; daemon will alert when ≤14 days remain)
- [ ] Provision a **public-read object store** (Cloudflare R2 free tier recommended): bucket + access key + HTTPS public URL prefix

### 4. Verify

```bash
python -m src verify-env
```

Pings GitHub, your chosen LLM, the IG token (if configured), and the image host. Reports issues.

## Commands

```bash
python -m src scan-repos        # GitHub Search API: rising repos → repos_seen
python -m src scan-hackathons   # Devpost scraper → hackathon_projects
python -m src evaluate          # LLM-evaluate any unevaluated rows (respects daily budget)
python -m src run               # Run TODAY'S full pipeline (Mon/Fri repo, Wed hackathon, else no-op)
python -m src run --day 2       # Force a specific weekday (0=Mon..6=Sun)
python -m src serve             # Read-only monitoring dashboard (http://localhost:8000)
python -m src daemon            # APScheduler daemon — fires daily at SCHEDULE_HOUR ±jitter
```

For testing without consuming Instagram quota: `IG_DRY_RUN=1` skips upload + publish but still renders + writes a `posts` row.

## Architecture

```
src/
├── config.py           Settings.from_env(), validates LLM key matches provider
├── db.py               sqlite3 conn, init_db, log_api_call (per-provider budget tracking)
├── models.py           Pydantic frozen contracts: Candidate, HackathonCandidate, Evaluation, Caption, RenderResult, PublishedPost
├── llm/
│   └── provider.py     LLMProvider protocol + ClaudeProvider, GeminiProvider, OpenAIProvider, get_provider(settings)
├── sources/
│   ├── github_repos/   Star-velocity scanner (preserved from previous build)
│   └── devpost/        BeautifulSoup scraper, robots.txt-respectful, rate-limited
├── evaluator/
│   ├── evaluator.py    evaluate_candidate (repo) + evaluate_hackathon
│   ├── batch.py        Daily budget guard, 7-day dedup, per-candidate isolation
│   ├── prompts.py      REPO_SYSTEM_PROMPT + HACKATHON_SYSTEM_PROMPT
│   └── fetcher.py      README + commits + issues for repo eval
├── caption/
│   └── generator.py    LLM caption (hook/body/CTA/hashtags), one provider call per post
├── render/
│   ├── renderer.py     Playwright (Chromium) HTML-to-JPEG @ 1080×1080
│   ├── templates/      Jinja2: repo_card.html + hackathon_slide_{1..4}.html
│   └── static/style.css
├── publisher/
│   ├── image_host.py   S3Host (boto3) for AWS/R2/B2, LocalFileHost for dev
│   ├── instagram.py    Graph API: container → wait → publish; single + carousel
│   ├── token_manager.py  60-day refresh + ≤14-day expiry alert
│   └── publisher.py    Render → upload → publish, with retry + idempotency
├── pipeline.py         run_repo_pipeline / run_hackathon_pipeline / run_for_today
├── scheduler/
│   └── daemon.py       APScheduler at SCHEDULE_HOUR ±SCHEDULE_JITTER_MINUTES
├── web/
│   ├── app.py          Read-only Flask dashboard (no scan/approval buttons)
│   ├── queries.py      Posts, evaluations, hackathons, scans, runs
│   └── templates/, static/
└── cli.py              Subcommands wired to all of the above
```

### Data model

`schema.sql` is auto-applied on every CLI invocation (idempotent). Key tables:

- `repos_seen` — natural key `full_name`. UPSERT on every scan to keep the next run's growth delta accurate.
- `hackathon_projects` — natural key `devpost_url`.
- `evaluations` — `content_type ∈ {repo, hackathon}`, FKs to either source. `skip` boolean from the LLM.
- `posts` — `media_type ∈ {single, carousel}`. `card_paths` + `image_host_urls` are JSON arrays. `status` lifecycle: `pending → rendered → uploaded → published` (or `failed`).
- `api_calls` — source of truth for daily LLM budget. Service column is `claude` / `gemini` / `openai` / `github` / `devpost` / `instagram`.

## Tests

```bash
pytest -q
```

Renderer tests mock Playwright (no browser binary needed for CI). IG / S3 tests mock HTTP. The full pipeline path is exercised end-to-end via the publisher tests with mocks.

## Operational notes

- **Posting times** are jittered ±15 min around `SCHEDULE_HOUR` per PRD risk #6.
- **Token refresh**: the daemon's daily 05:00 job calls `token_manager.check_and_alert`. When ≤14 days remain it logs a warning. To rotate: get a new short-lived token from Meta, run `python -m src verify-env` (or call `refresh_long_lived_token` directly).
- **Sandbox trial** (PRD Phase 4 — Docker for CLI tools, Playwright screenshot of demo URLs) is not implemented. The renderer module is the place to add demo-screenshot slides for hackathon carousels later.
- **GitHub trending scrape** (PRD §1, "secondary signal") is intentionally omitted — the PRD itself flags it as brittle. Search API only for v1.
