# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Discovery + post-generation pipeline for promising open-source projects. Discovers GitHub repos via the Search API + hackathon projects via Devpost scrape, evaluates with a pluggable LLM (Claude, Gemini, or OpenAI), generates captions, and renders 1080×1080 JPEGs via Playwright. **Posts are saved locally for human review** — no automatic upload or publishing. APScheduler daemon fires Mon repo / Wed hackathon carousel / Fri repo.

## Commands

All assume venv active and `.env` populated (see `.env.template`).

```bash
python -m src scan-repos        # GitHub Search API → repos_seen
python -m src scan-hackathons   # Devpost scrape → hackathon_projects
python -m src evaluate          # LLM-evaluate unevaluated rows (per-provider daily budget)
python -m src run               # Discover + evaluate + render + save post for today's content type
python -m src run --day 0       # Force a weekday (0=Mon..6=Sun)
python -m src serve             # Read-only monitoring dashboard
python -m src daemon            # APScheduler daemon
python -m src verify-env        # Smoke-test all configured external services

pytest -q                                     # full suite
pytest tests/sources/github_repos/ -q         # one package
pytest tests/render/test_renderer.py -q       # one file
```

`reporadar.db` is auto-created from `schema.sql` on every CLI invocation via `init_db()` (idempotent — `CREATE TABLE IF NOT EXISTS`). Rendered images land in `settings.output_dir` (default `output/`).

## Architecture

**Single SQLite DB underpins four stages: discovery → eval → caption → render.** All stages share `Settings` (`src/config.py`, loaded from `.env` via `Settings.from_env()`). Every CLI invocation creates a UUID `run_id` row in `pipeline_runs`; downstream rows in `evaluations`, `posts`, `api_calls` reference it.

### LLM provider abstraction (`src/llm/provider.py`)

`LLM_PROVIDER=claude|gemini|openai` selects between `ClaudeProvider` (anthropic SDK), `GeminiProvider` (google-generativeai SDK), and `OpenAIProvider` (OpenAI SDK Responses API). The default is `openai`. All expose `generate(prompt, system) -> str` and log to `api_calls` with `service` set to the provider name. The daily budget guard in `evaluator/batch.py` filters by the active provider's name.

### Discovery (`src/sources/`)

- `github_repos/scanner.scan()` — runs two Search API queries (newly-created + recently-pushed within `repo_max_age_days`), computes velocity via `velocity.compute_velocity()`. **Critical invariant:** every search hit gets UPSERTed to `repos_seen` even when below thresholds — that establishes the baseline for next run's delta calc. Brand-new repos fall back to fetching stargazer timestamps to estimate the window-start star count.
- `devpost/scanner.scan_devpost()` — polite scraper with rate limit + robots.txt check. Filters: must have GitHub link AND prize-winning status (per PRD §1). Non-eligible rows still get UPSERTed for tracking.

### Evaluation (`src/evaluator/`)

- `batch.evaluate_candidates` (repos) and `batch.evaluate_hackathon_candidates` (hackathons). Both: 7-day dedup, daily budget guard against the active provider, `max_evaluations_per_run` cap, per-candidate exception isolation.
- `evaluator.evaluate_candidate` builds prompt from `RepoContext` (README + commits + issues). `evaluator.evaluate_hackathon` uses `build_hackathon_prompt` directly (no fetcher).
- LLM JSON parsing is lenient: strips ```json fences, retries once with "return ONLY valid JSON" if first parse fails.
- Stores both `raw_response` (canonical) and `claude_raw_response` (legacy column name retained for back-compat with rows from earlier builds).

### Caption + Render (`src/caption/`, `src/render/`)

- `generate_repo_caption` / `generate_hackathon_caption` — provider-agnostic, returns a `Caption` Pydantic model. `Caption.render()` clips to ≤2,200 chars (Instagram caption limit retained as a sane upper bound).
- `render_repo_card` produces one 1080×1080 JPEG. `render_hackathon_carousel` produces 4 slides (hook → what it does → tech stack → team/links).
- Templates use Jinja2; CSS targets system fonts so no font binaries shipped. Renderer uses Playwright sync API + Chromium. Tests mock `sync_playwright` so they pass without browser binaries installed.
- Rendered files persist in `settings.output_dir` for the operator to review.

### Save (`src/publisher/publisher.py`)

`save_post` is the pipeline's hand-off step: writes the `posts` row at status `rendered`, idempotency-checks against existing rows for the same `repo_id`/`hackathon_id` (UNIQUE constraints back this up — a re-run updates the row in place), and flips the source's `already_posted=1` so subsequent runs skip it. Returns a `SavedPost` carrying `post_id`, `card_paths`, and the rendered caption.

There is no upload, no Instagram client, no token management, no retry logic. The operator reviews the local JPEGs plus the `caption` column and posts manually wherever they like.

### Orchestration (`src/pipeline.py`, `src/scheduler/daemon.py`)

- `run_for_today` dispatches on weekday: 0/4 → repo pipeline; 2 → hackathon pipeline.
- Scheduler fires at `SCHEDULE_HOUR:00` then sleeps a random 0..jitter*60 seconds before invoking the pipeline.

### Read-only dashboard (`src/web/`)

Shows: posts awaiting review (with caption + local image paths), recent evaluations (both content types), today's repo scans, recent hackathon candidates, recent runs.

## Key data model details (`schema.sql`)

- `repos_seen.full_name`, `hackathon_projects.devpost_url` are natural keys (UNIQUE). All UPSERTs hit them.
- `evaluations` has both `repo_id` and `hackathon_id` (one is NULL); `content_type` is the discriminator.
- `posts.repo_id` / `posts.hackathon_id` are UNIQUE — DB-level idempotency for "one saved post per source".
- `posts.status` lifecycle: `pending → rendered`, or `failed`.
- `api_calls` is the source of truth for daily budget counting. New LLM calls must log via the provider's `_log_call` helper (or directly via `db.log_api_call`) or budgets break silently.

## Models (`src/models.py`)

All `frozen=True`. Don't mutate; build new instances. `Evaluation.novelty_score / explainability_score / overall_score` are validated `1 ≤ x ≤ 10` at construction.

## Out of scope (deferred from PRD)

- **Auto-publishing to Instagram (or any other platform).** The PRD originally specified end-to-end automation through the IG Graph API; that has been removed in favor of a human review step. To reintroduce, add a publishing module under `src/publisher/` and wire it after `save_post`.
- **Sandbox trial** (PRD Phase 4 — Docker for CLI tools, Playwright demo screenshots): not implemented.
- **GitHub trending page scrape** (PRD §1 secondary signal): omitted; PRD risk #1 calls it brittle.
