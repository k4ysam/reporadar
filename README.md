# RepoRadar

Discovery + post-generation pipeline that finds trending GitHub repos and standout hackathon projects, evaluates them with an LLM, and renders Instagram-ready images. Posts are saved locally for human review — no automatic publishing.

```
GitHub Search API   → Velocity scan ┐
                                    ├─ LLM evaluation → pick top → Caption gen → Render → output/*.jpg
Devpost scraper     → Project scan ┘                                        (review locally)
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
| `OUTPUT_DIR` | rendering | local path where rendered post images are saved (default `output/`) |

### 3. Verify

```bash
python -m src verify-env
```

Pings GitHub, your chosen LLM, and confirms the output directory is writable. Reports issues.

## Commands

```bash
python -m src scan-repos        # GitHub Search API: rising repos → repos_seen
python -m src scan-hackathons   # Devpost scraper → hackathon_projects
python -m src evaluate          # LLM-evaluate any unevaluated rows (respects daily budget)
python -m src run               # Scan/evaluate repos + hackathons, then render the top candidate
python -m src serve             # Read-only monitoring dashboard (http://localhost:8000)
python -m src daemon            # APScheduler daemon — fires daily at SCHEDULE_HOUR ±jitter
```

A successful `run` prints the saved post id and the local image path(s). The image lives in `OUTPUT_DIR`; the caption is stored in the `posts.caption` column and visible in the dashboard.

## Architecture

```
src/
├── config.py           Settings.from_env(), validates LLM key matches provider
├── db.py               sqlite3 conn, init_db, log_api_call (per-provider budget tracking)
├── models.py           Pydantic frozen contracts: Candidate, HackathonCandidate, Evaluation, Caption, RenderResult, SavedPost
├── llm/
│   └── provider.py     LLMProvider protocol + ClaudeProvider, GeminiProvider, OpenAIProvider, get_provider(settings)
├── sources/
│   ├── github_repos/   Star-velocity scanner
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
│   └── publisher.py    save_post — write the rendered post to the DB for human review
├── pipeline.py         run_pipeline across repo + hackathon candidates
├── scheduler/
│   └── daemon.py       APScheduler at SCHEDULE_HOUR ±SCHEDULE_JITTER_MINUTES
├── web/
│   ├── app.py          Read-only Flask dashboard
│   ├── queries.py      Posts, evaluations, hackathons, scans, runs
│   └── templates/, static/
└── cli.py              Subcommands wired to all of the above
```

### Data model

`schema.sql` is auto-applied on every CLI invocation (idempotent). Key tables:

- `repos_seen` — natural key `full_name`. UPSERT on every scan to keep the next run's growth delta accurate.
- `hackathon_projects` — natural key `devpost_url`.
- `evaluations` — `content_type ∈ {repo, hackathon}`, FKs to either source. `skip` boolean from the LLM.
- `posts` — `media_type ∈ {single, carousel}`. `card_paths` is a JSON array of local file paths. `status` lifecycle: `pending → rendered` (or `failed`).
- `api_calls` — source of truth for daily LLM budget. Service column is `claude` / `gemini` / `openai` / `github` / `devpost`.

## Tests

```bash
pytest -q
```

Renderer tests mock Playwright (no browser binary needed for CI). The full pipeline path is exercised via the publisher tests with seeded fixtures.

## Operational notes

- **Reviewing posts.** `python -m src serve` lists posts awaiting review with their image paths and caption text. Open the JPEGs from `OUTPUT_DIR` and post wherever you like.
- **Posting cadence** is jittered ±15 min around `SCHEDULE_HOUR` per PRD risk #6.
- **Re-running for the same source** updates the existing post row in place (UNIQUE on `repo_id`/`hackathon_id`).
- **Sandbox trial** (PRD Phase 4 — Docker for CLI tools, Playwright screenshots) is not implemented.
- **GitHub trending scrape** (PRD §1, "secondary signal") is intentionally omitted.
