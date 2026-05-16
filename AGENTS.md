# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## What this is

Discovery + post-generation pipeline for promising open-source projects. Discovers GitHub repos via the Search API + hackathon projects via Devpost scrape, evaluates both pools with a pluggable LLM (Codex, Gemini, or OpenAI), generates per-channel captions and posters (Instagram 1:1, LinkedIn 2:3), and writes one `posted_repositories` row per selected project. **Posts are saved locally for human review** — no automatic upload or publishing. APScheduler daemon runs the pipeline daily.

The codebase is organized as v2 microservice modules (see `Doc/reporadar_v2_architecture.md`). Each top-level folder under `src/` is one service.

## Commands

All assume `.venv/` active and `.env` populated (see `.env.template`).

```bash
.venv/bin/python migrations/apply.py        # Apply Postgres schema to Supabase
python -m src scan-repos                    # GitHub Search API → candidate_repository_evaluations
python -m src scan-hackathons               # Devpost scrape → candidate_repository_evaluations
python -m src evaluate                      # LLM-evaluate pending candidates
python -m src run                           # Full pipeline (discover → evaluate → select → generate → render → export)
python -m src submit <url>                  # Manually submit a GitHub/Devpost URL
python -m src serve                         # Read-only monitoring dashboard
python -m src daemon                        # APScheduler daemon
python -m src verify-env                    # Smoke-test all configured external services

pytest -q                                          # full suite (48 tests, no DB / no network)
pytest tests/selection/ -q                         # one service
pytest tests/candidate_intelligence/evaluation/ -q # one package
```

The schema lives in `migrations/0001_initial_v2.sql`. The migration runner is idempotent — every CREATE uses `IF NOT EXISTS`. Re-run anytime.

## Architecture (v2)

Services are organized as **modular microservices that talk synchronously via Python imports today** (the event-bus split in `Doc/reporadar_v2_architecture.md` §26 Phase 6 is future work). Each service owns one bounded responsibility and its own JSONB section of the database.

```
src/
├── common/                # Settings, Postgres connection, logger, ID helpers
├── contracts/             # Cross-service Pydantic models (frozen)
├── ai_gateway/            # LLM + image-provider adapters
├── candidate_intelligence/   # Discovery + enrichment + evaluation + dedup
│   ├── source_adapters/{github_discovery,devpost_discovery,manual_submission}
│   ├── enrichment/
│   ├── evaluation/
│   ├── deduplication/
│   └── repository.py      # Owns the candidate_repository_evaluations table
├── selection/             # Rank + score-breakdown logic; picks the winner
├── content_generation/    # Per-channel text (instagram caption, linkedin commentary)
├── media_rendering/       # Per-channel image profiles + prompt builders
├── post_packaging/        # Combines content + media + validation rules → PostPackage
├── publishing/            # Manual-export adapter; owns posted_repositories table
├── orchestrator/          # Pipeline workflow only — no business logic
├── scheduler/             # APScheduler daemon → calls orchestrator
└── operator_api/          # CLI commands + Flask read-only dashboard
```

### Key rules

- **Each service owns its data section.** `candidate_intelligence/repository.py` is the only writer of `candidate_repository_evaluations`; `publishing/repository.py` is the only writer of `posted_repositories`. The dashboard reads via `operator_api/web/queries.py` — never directly across service tables.
- **Orchestrator contains no business logic.** It assembles a run by calling each service's public entry point (`discover_and_evaluate`, `select_top_candidate`, `generate_content`, `render_media`, `build_post_package`, `publish_packages`). Adding a new channel = adding a new media profile + content template + channel validator; the orchestrator doesn't change.
- **`OPENAI_API_KEY` is always required** even when `LLM_PROVIDER` is `Codex` or `gemini`, because image generation goes through `OpenAIImageClient` regardless. `Settings.provider_key_present` enforces this at config-load time.
- **Discovery upserts every search hit** (eligible or not) to `candidate_repository_evaluations` so the next run has a baseline for delta calc.

### Data model (v2)

Two JSONB-rich Postgres tables per `Doc/reporadar_database_design.md`:

```
candidate_repository_evaluations
  id, run_id, project_id, canonical_repo_key, source_type, status,
  source / discovery / github / hackathon / enrichment / deduplication
  / evaluation / ranking / selection / post_link / audit  (all JSONB)

posted_repositories
  id, project_id, canonical_repo_key, canonical_repo_url,
  github / hackathon / project_description / source / evaluation_snapshot
  / ranking_snapshot / post_instances (array of channels) / posting_state / audit
```

Plus operational `pipeline_runs` and `api_calls` tables.

`canonical_repo_key` is the universal cross-source identity: `github:owner/repo` or `devpost:<slug>`. `project_id` is derived deterministically from `canonical_repo_key` via SHA-1 (see `src/common/ids.project_id_for`), so the same repo discovered across many runs maps to one project identity without a lookup table.

### LLM provider abstraction (`src/ai_gateway/llm/`)

`LLM_PROVIDER=Codex|gemini|openai` selects between `ClaudeProvider`, `GeminiProvider`, and `OpenAIProvider`. Default is `openai`. All providers expose `generate(prompt, system) -> str` and log to `api_calls` via `_BaseProvider._log_call`.

### Channels

Adding a channel:

1. Add a per-channel content template in `src/content_generation/channels/<channel>/` and route it from `src/content_generation/service.py`.
2. Add a `ChannelMediaProfile` in `src/media_rendering/channels/__init__.py` (width/height/aspect/prompt builder).
3. Add a per-channel validator in `src/post_packaging/channels/<channel>_package.py`.

Today `instagram` (1:1, 1024×1024) and `linkedin` (2:3, 1024×1536) are wired.

## Database

Production DB is **Supabase Postgres** via `DATABASE_URL` (transaction-pooler URL on port 6543). The runtime layer is `psycopg 3`; `src/common/db.py` wraps connection + observability logging.

If the password in `DATABASE_URL` contains reserved URI characters (`@`, `/`, `:`, `#`), URL-encode them (`@` → `%40`) — psycopg parses the URI strictly.

To apply or refresh the schema:

```bash
.venv/bin/python migrations/apply.py
```

The migration is idempotent. No `init_db()`-style auto-setup is done on every CLI call any more.

## Contracts (`src/contracts/`)

All `frozen=True`. Don't mutate; build new instances with `.model_copy(update=...)`. `EvaluationScores` fields are validated `1 ≤ x ≤ 10` at construction.

## Out of scope (Phase 6+ in v2 doc)

- **Async event bus** (Redis Streams / RabbitMQ). Today services talk synchronously via Python imports inside the same process.
- **Dockerized per-service deployment.** Today everything runs in one Python process invoked by the CLI / daemon.
- **Operator API approve/reject/regenerate endpoints.** Dashboard is read-only; route stubs in `src/operator_api/cli.py` only.
- **Auto-publishing to Instagram / LinkedIn.** Removed in favor of manual export. To reintroduce, add an adapter under `src/publishing/adapters/` and call it after `export_to_disk` in `publishing/service.py`.
