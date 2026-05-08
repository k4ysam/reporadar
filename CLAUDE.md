# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

All commands assume the venv is active (`source .venv/bin/activate`) and `.env` exists with `GH_TOKEN` and `GEMINI_API_KEY` set.

```bash
python -m src scan         # find rising repos, persist to repos_seen
python -m src evaluate     # score unevaluated repos with Gemini
python -m src serve        # Flask dashboard at http://localhost:8000

python -m pytest tests/ -q                              # full suite
python -m pytest tests/scanner/test_velocity.py -q      # single file
python -m pytest tests/scanner/test_velocity.py::test_name -q   # single test
```

The DB at `reporadar.db` is auto-created from `schema.sql` on every CLI invocation via `init_db()` (idempotent — uses `CREATE TABLE IF NOT EXISTS`).

## Architecture

**Three-stage pipeline backed by a single SQLite DB.** The CLI dispatches to `cmd_scan`, `cmd_evaluate`, or `cmd_serve` (`src/cli.py`). All three stages share the same DB schema (`schema.sql`) and the same `Settings` config object loaded from `.env` via `Settings.from_env()` (`src/config.py`).

**Every pipeline invocation gets a UUID `run_id`** recorded in `pipeline_runs` with `status` (`running`/`completed`/`failed`). Downstream rows in `api_calls` and `evaluations` reference it. This is how budget tracking and observability work — see `_gemini_calls_today()` in `src/evaluator/batch.py`, which counts today's `api_calls.service='gemini'` rows to enforce `GEMINI_DAILY_LIMIT`.

**Scan stage** (`src/scanner/`):
- `scanner.scan()` runs two GitHub Search queries (newly-created repos, recently-pushed repos within `repo_max_age_days`) and computes velocity via `velocity.compute_velocity()`.
- **Critical invariant:** every repo returned by the search is UPSERTed into `repos_seen` with current `star_count_at_last_scan`, even if it doesn't pass velocity thresholds. This is what makes the next run's growth delta accurate — first sighting establishes the baseline; subsequent sightings compare against it. For brand-new repos (no prior row), `compute_velocity` falls back to fetching stargazer timestamps to estimate the window-start star count.
- Filters out repos where `already_posted=1` or `excluded_until >= today`.

**Evaluate stage** (`src/evaluator/`):
- Pulls repos from `repos_seen` that have no row in `evaluations` and aren't already posted.
- `batch.evaluate_candidates()` enforces two budgets: `MAX_EVALUATIONS_PER_RUN` and `GEMINI_DAILY_LIMIT` (the latter spans calendar days, read from the `api_calls` log).
- Skips anything evaluated in the last 7 days.
- `evaluator.evaluate_candidate()` builds a prompt from `RepoContext` (README + recent commits + top issues, fetched in `fetcher.py`) and calls Gemini. JSON parsing is lenient — strips ```json fences, retries once with "return ONLY valid JSON" if first parse fails.
- The prompt builder in `prompts.py` returns Anthropic-style content blocks with `cache_control` for long READMEs, then `blocks_to_text()` flattens them for Gemini. This is leftover Anthropic structure — see "PRD ↔ code mismatch" below.

**Serve stage** (`src/web/app.py`):
- Flask dashboard. The `/scan` POST handler invokes the same `scanner.scan()` function the CLI uses, but allows overriding `velocity_window_hours` per-request and persists the override into the `app_settings` table so reads stay consistent.

**Config precedence:** `.env` is loaded by `python-dotenv` at import time (`src/config.py`), so any code that imports `Settings` after that will see env vars. `app_settings` (DB-backed) is read by `_window_days()` in the web layer to override `velocity_window_hours` for dashboard-triggered scans only — CLI scans use the env-derived `Settings` value.

## Key data model details (`schema.sql`)

- `repos_seen.full_name` is the natural key (UNIQUE). All UPSERTs hit it.
- `evaluations.repo_id` → `repos_seen.id` (the autoincrement int, NOT `github_repo_id`). The evaluator INSERT does the lookup inline via `INSERT … SELECT id FROM repos_seen WHERE full_name=?`.
- `api_calls` is the source of truth for daily budget counting. If you add a new LLM call path, log it via `log_api_call()` or budget enforcement breaks silently.
- `pipeline_runs.status` has a CHECK constraint — only `running`/`completed`/`failed` are valid.

## Pydantic models (`src/models.py`)

`Candidate` and `Evaluation` are `frozen=True` — they're immutable value objects. Don't try to mutate them; build new ones. `Evaluation` enforces `1 <= scores <= 10` at construction.

## PRD ↔ code mismatch worth knowing

`prd.md` Step 3 specifies "Claude API" for evaluation. The code uses **Google Gemini** (`google-generativeai` SDK, default model `gemini-2.0-flash`). Vestiges of the original Anthropic implementation remain — `evaluations.claude_raw_response` column name, the content-block shape in `prompts.build_user_prompt_blocks` with `cache_control`. If you change the LLM provider, both the SDK call and the prompt-block flattening (`blocks_to_text`) need updating, plus the budget guard's `service='gemini'` literal.

## Testing notes

- `tests/conftest.py` provides `tmp_db` (calls `init_db()` against a tmp file) and `mock_run_id`. Use these for any test that needs DB state.
- HTTP calls are stubbed via `responses` (see `tests/scanner/test_github_client.py`). The Gemini client is mocked directly in evaluator tests.
- `pyproject.toml` sets `pythonpath = ["."]` and `testpaths = ["tests"]` — tests import from `src.*` without any path manipulation.
