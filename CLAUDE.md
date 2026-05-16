# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Discovery + post-generation pipeline for promising open-source projects. Discovers GitHub repos via the Search API + hackathon projects via Devpost scrape, evaluates both pools with a pluggable LLM (Claude, Gemini, or OpenAI), generates per-channel captions and posters (Instagram 1:1, LinkedIn 2:3), and writes one `posted_repositories` row per selected project. **Posts are saved locally for human review** — no automatic upload or publishing. APScheduler daemon runs the pipeline daily.

The codebase is organized as v2 microservice modules (see `Doc/reporadar_v2_architecture.md`). Each top-level folder under `src/` is one service.

## Service docs — read before changing, update after changing

Every service in `src/` has a dedicated doc under `Doc/services/`. **These are the source of truth for how each service works, what it owns, and how it talks to the rest of the system.**

| Service | Doc |
|---|---|
| `src/candidate_intelligence/` | [Doc/services/candidate_intelligence.md](Doc/services/candidate_intelligence.md) |
| `src/content_generation/` | [Doc/services/content_generation.md](Doc/services/content_generation.md) |
| `src/publishing/` | [Doc/services/publishing.md](Doc/services/publishing.md) |
| `src/orchestrator/` | [Doc/services/orchestrator.md](Doc/services/orchestrator.md) |
| `src/scheduler/` | [Doc/services/scheduler.md](Doc/services/scheduler.md) |
| `src/operator_api/` | [Doc/services/operator_api.md](Doc/services/operator_api.md) |

Plus an index at [Doc/services/README.md](Doc/services/README.md) with the cross-service map.

**Rules for agents working on this repo:**

1. **Before changing a service**, read its doc. Each doc describes the service's purpose, internal stages, entry points, data ownership, state machine, and what's intentionally out of scope. Understanding these constraints prevents accidentally violating ownership boundaries (e.g. writing to another service's table) or breaking the orchestrator's workflow-only invariant.
2. **After changing a service**, update its doc *in the same change* so the docs never drift. Update anything affected: source layout, internal pipeline, entry-point signatures, data ownership, state machine, configuration knobs, failure modes, or "out of scope" notes. If your change spans services (e.g. new contract field), update every affected service's doc.
3. **When adding a new service**, follow the structure of the existing docs and add an entry to `Doc/services/README.md`. Cross-link the new doc from the docs of any service it interacts with.
4. **When adding a new channel**, no new doc is needed — but update the "Adding a new channel" / channels sections of `Doc/services/content_generation.md`.

If a doc contradicts the code, the code is right; fix the doc in the same change. Treat doc drift as a code review blocker.

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

pytest -q                                          # full suite (51 tests, no DB / no network)
pytest tests/candidate_intelligence/ -q            # one service
pytest tests/candidate_intelligence/evaluation/ -q # one package
```

The schema lives in `migrations/0001_initial_v2.sql`. The migration runner is idempotent — every CREATE uses `IF NOT EXISTS`. Re-run anytime.

## Architecture (v2)

Services are organized as **modular microservices that talk synchronously via Python imports today** (the event-bus split in `Doc/reporadar_v2_architecture.md` §26 Phase 6 is future work). Each service owns one bounded responsibility and its own JSONB section of the database.

There are **6 microservices** plus 3 shared infra modules (`common/`, `contracts/`, `ai_gateway/`):

```
src/
├── common/                          # Settings, Postgres connection, logger, IDs
├── contracts/                       # Cross-service Pydantic models (frozen)
├── ai_gateway/                      # LLM + image-provider adapters
│
├── candidate_intelligence/          # Service 1: "what should we post next?"
│   ├── service.py                   #   top-level: discover_evaluate_and_select
│   ├── repository.py                #   owns candidate_repository_evaluations
│   ├── source_adapters/             #   stage 1: discovery
│   │   ├── github_discovery/
│   │   ├── devpost_discovery/
│   │   └── manual_submission.py
│   ├── enrichment/                  #   stage 2: README + commits + issues
│   ├── evaluation/                  #   stage 3: LLM scoring
│   ├── selection/                   #   stage 4: ranking + picking the winner
│   │   ├── ranking.py
│   │   └── selector.py
│   └── deduplication/               #   utility: canonical key derivation
│
├── content_generation/              # Service 2: "build the platform-ready post"
│   ├── service.py                   #   top-level: generate_post_package
│   ├── text/                        #   stage 1: per-channel text
│   │   ├── service.py
│   │   └── channels/{instagram,linkedin}.py
│   ├── media/                       #   stage 2: per-channel image rendering
│   │   ├── service.py
│   │   ├── profile.py               #   ChannelMediaProfile dataclass
│   │   ├── style.py                 #   shared prompt building blocks
│   │   └── channels/                #   {instagram,linkedin}.py = profile + prompt
│   └── packaging/                   #   stage 3: assembly + validation
│       ├── service.py
│       └── channels/{instagram,linkedin}.py
│
├── publishing/                      # Service 3: writes posted_repositories + sidecars
├── orchestrator/                    # Service 4: pipeline workflow (no business logic)
├── scheduler/                       # Service 5: APScheduler daemon
└── operator_api/                    # Service 6: CLI + Flask dashboard
```

(Review Dashboard and Project Registry services from v2 §2 are folded into `operator_api` and `candidate_intelligence` respectively for the MVP.)

### Key rules

- **Each service owns its data section.** `candidate_intelligence/repository.py` is the only writer of `candidate_repository_evaluations` (including the `ranking` and `selection` sections, now that Selection is an internal stage). `publishing/repository.py` is the only writer of `posted_repositories`. The dashboard reads via `operator_api/web/queries.py` — never directly across service tables.
- **Orchestrator contains no business logic.** Three service calls per run:
  ```python
  selection = discover_evaluate_and_select(conn, settings, run_id, provider, channels=...)
  for channel in selection.selected_for_channels:
      package = generate_post_package(conn, settings, run_id, candidate, evaluation, provider, channel=channel)
  publish_packages(conn, settings, candidate=..., evaluation=..., selection=..., packages=...)
  ```
- **`OPENAI_API_KEY` is always required** even when `LLM_PROVIDER` is `claude` or `gemini`, because image generation goes through `OpenAIImageClient` regardless. `Settings.provider_key_present` enforces this at config-load time.
- **Discovery upserts every search hit** (eligible or not) to `candidate_repository_evaluations` so the next run has a baseline for delta calc.
- **Adding a new channel** = adding a new file in three places (one per Content Generation stage):
  `text/channels/<channel>.py`, `media/channels/<channel>.py` (+ entry in `media/channels/__init__.PROFILES`), `packaging/channels/<channel>.py` (+ entry in `packaging/channels/__init__.VALIDATORS`). No orchestrator change required.

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

`LLM_PROVIDER=claude|gemini|openai` selects between `ClaudeProvider`, `GeminiProvider`, and `OpenAIProvider`. Default is `openai`. All providers expose `generate(prompt, system) -> str` and log to `api_calls` via `_BaseProvider._log_call`.

### Channels

Today `instagram` (1:1, 1024×1024) and `linkedin` (2:3, 1024×1536) are wired. To add another, see the *Adding a new channel* section of [Doc/services/content_generation.md](Doc/services/content_generation.md) — three files (one per Content Generation stage), no orchestrator change.

## Database

Production DB is **Supabase Postgres** via `DATABASE_URL` (transaction-pooler URL on port 6543). The runtime layer is `psycopg 3`; `src/common/db.py` wraps connection + observability logging.

`src/common/db.py` opens every connection with **`autocommit=True, prepare_threshold=None`**. Both are mandatory for the Supabase transaction pooler:

- `prepare_threshold=None` disables psycopg's auto-prepare. The pooler reuses backend connections across client transactions; a server-side prepared statement registered on one backend will not exist on the next, producing `psycopg.errors.InvalidSqlStatementName: prepared statement "_pg3_N" does not exist`.
- `autocommit=True` prevents a single failed statement from leaving the connection stuck in `INTRANS_ERROR`, which would block every subsequent write (including `finish_run`) with `psycopg.errors.InFailedSqlTransaction`.

Every repository helper writes single statements and calls `conn.commit()` — those commits are no-ops in autocommit mode (psycopg silently ignores them). If you ever need multi-statement atomicity, wrap the block with `with conn.transaction():`.

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
