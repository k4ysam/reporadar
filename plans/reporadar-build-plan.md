# RepoRadar — Build Plan
**Project:** Automated GitHub Discovery Newsletter (Telegram digest + Instagram publishing)
**Generated:** 2026-05-02 | **Last updated:** 2026-05-03
**Mode:** Direct (no GitHub CLI dependency)
**Steps:** 9 across 3 phases — validate signal before touching social media APIs

---

## Build Philosophy

**Phase 1 (Steps 1–3): Prove the signal.**
Build and validate the core pipeline in isolation — no Telegram, no Instagram, no image cards. A local web dashboard replaces Telegram for the initial review loop: run the scanner, evaluate with Gemini, inspect results at localhost:8000. This phase is complete.

**Phase 2 (Steps 4–5): Add the human loop.**
Wire in Telegram so you can approve/reject evaluations from your phone. Run a week of real digests before touching Instagram. The local dashboard continues to serve as an operational view alongside Telegram.

**Phase 3 (Steps 6–8): Publishing pipeline.**
Build image cards and the Instagram publisher only after the signal quality is confirmed. Account provisioning (Step 0) starts at the beginning of Phase 3.

---

## Architectural Decisions (deviations from original plan)

| Decision | Original plan | What was built | Reason |
|----------|--------------|----------------|--------|
| LLM provider | Anthropic Claude | Google Gemini (`gemini-2.0-flash`) | No Anthropic key; Gemini free tier available |
| Phase 1 review UI | CLI only | Flask dashboard at `localhost:8000` | Easier to browse results visually |
| Scan trigger | CLI only | CLI + "Scan Now" button in dashboard | Convenience |
| LLM daily budget guard | Not planned | `gemini_daily_limit` config + `api_calls` check | Free tier is 20 calls/day |
| Repo age filter | Not planned | `repo_max_age_days=365` added to search query | `pushed:>` query returned established mega-repos |
| Window setting | CLI env var | Persisted in `app_settings` DB table, editable in UI | Multi-day window (1–7d) needed |
| GitHub PAT scopes | `repo` + `read:user` | No scopes needed | Public repo access requires zero permissions |

---

## Dependency Graph

```
Phase 1 — Core pipeline (validate signal)  ✅ COMPLETE
  Step 1  (scaffold)           ✅
     ↓
  Step 2A (scanner)            ✅
     ↓
  Step 3  (Gemini evaluation)  ✅
     ↓
  Local dashboard              ✅
     ↓
  *** VALIDATE: run daily, confirm signal quality ***

Phase 2 — Human review loop (next)
  Step 4  (Telegram digest + approval)
     ↓
  *** VALIDATE: run a week of real digests ***

Phase 3 — Publishing (start Step 0 account setup here)
  Step 0  (external account provisioning — parallel with Steps 5–6)
  Step 5  (Pillow image card)
     ↓
  Step 6  (Instagram publisher)
     ↓
  Step 7  (APScheduler orchestrator)
     ↓
  Step 8  (Deployment hardening)
```

---

## ✅ Step 1 — Project Scaffold
**Status:** COMPLETE
**Commit:** `feat: project scaffold — models, DB, config, logger`

### What was built
- Python 3.12, Pydantic v2 frozen models as inter-module contracts
- SQLite schema (`schema.sql`) with all 5 tables upfront: `pipeline_runs`, `repos_seen`, `evaluations`, `posts`, `api_calls`, `app_settings`
- `src/config.py`: env-var loader with required-key validation, `Settings.from_env()`
- `src/db.py`: WAL mode, FK enforcement, `init_db()`, `log_api_call()`, `get_app_setting()`, `set_app_setting()`
- `src/logger.py`: structured logging with `run_id` context
- `src/models.py`: `Candidate`, `Evaluation`, `PipelineRun` (frozen Pydantic v2)
- `.env.template` with phase-gated comments
- Full test suite: `tests/test_models.py`, `tests/test_db.py`, `tests/test_config.py`

### Key config fields
```
GH_TOKEN, GEMINI_API_KEY, LLM_MODEL=gemini-2.0-flash
DB_PATH=reporadar.db, MAX_CANDIDATES_PER_RUN=15, MAX_EVALUATIONS_PER_RUN=5
GEMINI_DAILY_LIMIT=20, STAR_GROWTH_MIN_PCT=50, STAR_BASE_MIN=10
VELOCITY_WINDOW_HOURS=72, REPO_MAX_AGE_DAYS=365
```

---

## ✅ Step 2A — Star Velocity Scanner
**Status:** COMPLETE
**Commits:** `feat: star velocity scanner`, `fix: date bug + lower thresholds`, `feat: scan UI + repo age filter`

### What was built
- `src/scanner/github_client.py`: `GithubClient` with `_request()` (429 backoff, api_calls logging), `search_repos()`, `get_stargazers_with_timestamps()` (early-exit)
- `src/scanner/velocity.py`: delta-based for known repos, stargazer-page fetch for new repos, filters by `star_base_min` / `star_growth_min_pct` / `already_posted` / `excluded_until`
- `src/scanner/scanner.py`: rate-limit check, 2 search queries (see below), dedup, upsert repos_seen even when velocity returns None (critical for delta accuracy), sort by growth_pct

### Search query design
```python
window_start    = now - velocity_window_hours          # e.g. 3 days ago
max_age_cutoff  = now - repo_max_age_days              # e.g. 1 year ago

queries = [
    f"created:>{window_start} stars:>={star_base_min} sort:stars-desc",
    f"pushed:>{window_start} created:>{max_age_cutoff} stars:>={star_base_min} sort:updated",
]
```
The `created:>{max_age_cutoff}` guard on the pushed query prevents established mega-repos (pytorch, immich, etc.) from appearing — they get pushed to daily but aren't "rising".

### Tests
`tests/scanner/test_velocity.py`, `test_scanner.py`, `test_github_client.py` — 68 tests total, all passing.

---

## ✅ Step 3 — Gemini Evaluation Agent
**Status:** COMPLETE
**Commits:** `feat: Claude evaluation agent with prompt caching`, `feat: swap Anthropic for Google Gemini`

### What was built
- `src/evaluator/fetcher.py`: `fetch_repo_context()` — README, recent commits, open issues, description, topics, language
- `src/evaluator/prompts.py`: `SYSTEM_PROMPT`, `build_user_prompt_blocks()`, `blocks_to_text()` (flattens Anthropic-style blocks to a flat string for Gemini)
- `src/evaluator/evaluator.py`: `evaluate_candidate()` — calls `llm_client.generate_content()`, parses JSON, strips code fences, retries once on bad JSON, writes to `evaluations` table
- `src/evaluator/batch.py`: `evaluate_candidates()` — 7-day dedup, daily Gemini budget guard (checks `api_calls` table), `max_evaluations_per_run` cap, per-candidate exception isolation

### Gemini integration notes
- `genai.configure(api_key=...)` + `genai.GenerativeModel(model_name=..., system_instruction=SYSTEM_PROMPT)`
- `resp = llm_client.generate_content(prompt_text)` → `resp.text`
- Free tier: **20 calls/day**, 15 RPM. `GEMINI_DAILY_LIMIT=20` is enforced in `batch.py` before any call is made.
- `claude_raw_response` column name kept in schema (just a storage field — rename when relevant).

### Tests
`tests/evaluator/test_evaluator.py`, `test_batch.py` — mocks use `generate_content.return_value = MagicMock(text=JSON_STR)`.

---

## ✅ Step 3B — Local Web Dashboard
**Status:** COMPLETE
**Commits:** `feat: local web dashboard for scan results`

### What was built
- `src/web/app.py`: Flask app factory, `score_class` template global, `/` dashboard route, `/scan` POST endpoint
- `src/web/queries.py`: `get_todays_scans()` (LEFT JOIN evaluations for growth_pct), `get_evaluations_for_today()`, `get_recent_runs()`
- `src/web/templates/dashboard.html`: scan controls bar (window selector 1–7d + Scan Now button), scanned repos table, evaluation cards with score badges, recent pipeline runs table
- `src/web/static/style.css`: GitHub dark theme (#0d1117), score color coding, status pills, scan controls

### Dashboard features
- **Scan Now**: POST `/scan` runs the scanner synchronously; result message appears in UI
- **Window selector**: 1d/2d/3d/4d/5d/7d buttons — selection persisted in `app_settings` DB table, overrides `velocity_window_hours` for that run
- **Evaluations**: cards showing N/E/O scores, summary, why_interesting, audience, approval status
- **Flash messages**: scan result or error shown inline after redirect

### Running
```bash
python -m src serve          # starts at http://localhost:8000
python -m src scan           # CLI alternative
python -m src evaluate       # evaluates unevaluated repos (up to GEMINI_DAILY_LIMIT remaining)
```

---

## Step 4 — Telegram Review Bot
**Status:** NOT STARTED
**Phase:** 2
**Depends on:** Steps 1–3 + local dashboard validation (run daily for a few days first)

### Context
Once signal quality is confirmed via the dashboard, add Telegram so evaluations can be approved/rejected from a phone. The bot sends formatted digest messages with inline Approve/Reject buttons. Approvals will trigger the publishing hook in Phase 3.

### Task List

#### Bot Core (`src/digest/bot.py`)
- [ ] `RepoRadarBot` using `python-telegram-bot` Application builder
- [ ] `send_evaluation_digest(evaluation: Evaluation, db) -> int` (returns `telegram_message_id`)
  - Format message (repo name, star velocity, summary, scores, github link)
  - Inline keyboard: `[✅ Approve | ❌ Reject]` with callback_data `approve:{eval_id}` / `reject:{eval_id}`
  - Callback data limit: 64 bytes — use integer `evaluation_id`, not full_name
  - Store `telegram_message_id` in `evaluations` row
- [ ] `handle_callback(update, context)`:
  - Parse action + `evaluation_id` from callback data
  - Update `evaluations.approved` = 1 or 0, set `reviewed_at`
  - Edit original message to replace buttons with "✅ Approved" / "❌ Rejected"
  - Call `on_approval_hook(evaluation_id)` (stub → real publisher in Phase 3)

#### Message Formatter (`src/digest/formatter.py`)
- [ ] `format_digest_message(evaluation: Evaluation) -> str`
  ```
  🔭 *{repo_name}*
  ⭐ {stars_48h} stars in 72hrs (+{growth_pct:.0f}%)

  {summary}

  *Why now:* {why_interesting}
  *For:* {audience}

  📊 Novelty: {novelty}/10 · Explain: {explain}/10 · Overall: {overall}/10
  🔗 https://github.com/{full_name}
  ```
- [ ] MarkdownV2 escaping

#### Auto-Expiry (`src/digest/expiry.py`)
- [ ] `expire_stale_evaluations(db, max_age_hours=48)`: set `auto_expired=1` on old pending evaluations, send Telegram alert

#### Add to CLI (`src/cli.py`)
- [ ] `python -m src digest` — sends all pending unapproved evaluations to Telegram

#### Tests
- [ ] `tests/digest/test_formatter.py`: snapshot of formatted message
- [ ] `tests/digest/test_bot_callback.py`: mock Telegram update, assert DB updated
- [ ] `tests/digest/test_expiry.py`: stale evaluation auto-expires

#### Config additions (`.env`)
```
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

### Verification
```bash
python -m pytest tests/digest/ -v
python -m src digest   # manual: messages arrive in Telegram with working buttons
```

### Exit Criteria
- Formatted message with inline buttons arrives in Telegram
- Approve/Reject callback correctly updates DB `approved` field
- Auto-expiry runs without error on mock data

---

## Step 0 — External Account Provisioning
**Phase:** 3 (start when Phase 2 validated)
**Blocks:** Step 6 only
**Lead time risk:** Instagram Graph API review can take days–weeks.

### Checklist

#### GitHub (already done ✅)
- [x] GitHub PAT — no scopes needed for public repos; 5,000 req/hr authenticated

#### Gemini (already done ✅)
- [x] API key from aistudio.google.com; model pinned to `gemini-2.0-flash`

#### Telegram (Step 4)
- [ ] Create bot via @BotFather → `/newbot` → copy `TELEGRAM_BOT_TOKEN`
- [ ] Get chat ID: message the bot → `GET https://api.telegram.org/bot<TOKEN>/getUpdates`

#### Meta / Instagram Graph API
- [ ] Create Facebook Business account
- [ ] Create Meta Developer app at developers.facebook.com
- [ ] Convert Instagram account to Business or Creator (requires linked Facebook Page)
- [ ] Add Instagram Graph API product to the app
- [ ] Request `instagram_content_publish` permission (app review — submit early)
- [ ] Generate long-lived Page Access Token (60-day expiry → implement rotation reminder)

#### Image Hosting (required for Instagram)
- [ ] Choose: Cloudflare R2 (free tier) OR AWS S3 OR Backblaze B2
- [ ] Create bucket with public read access, HTTPS URL
- [ ] Verify: upload test image, confirm public URL accessible

---

## Step 5 — Image Card Generator
**Phase:** 3
**Depends on:** Step 0 setup + confirmed evaluation output quality

### Task List
- [ ] `src/cards/renderer.py`: `render_card(evaluation, output_path) -> str`
  - 1080×1080 PNG, dark background (#0d1117)
  - Repo name in large monospace font (white)
  - Star velocity stat in accent color: `+{stars_72h} ⭐ in 72hrs`
  - Summary tagline (≤80 chars)
  - Footer: `github.com/{full_name}` + RepoRadar branding
- [ ] Bundle OFL-licensed monospace font (JetBrains Mono or Fira Code) in `src/cards/fonts/`
- [ ] Tests: render with mock Evaluation, assert valid PNG, no crash on `language=None`

### Exit Criteria
- `cards/test_output.png` renders correctly
- Renders in <2 seconds

---

## Step 6 — Instagram Publisher
**Phase:** 3
**Depends on:** Step 0 (Instagram token + image hosting) + Step 5 (card)

### Task List
- [ ] `src/publisher/image_host.py`: `upload_card(path) -> HTTPS_URL` (R2/S3 via boto3)
- [ ] `src/publisher/caption.py`: `generate_caption(evaluation) -> str` (≤2,200 chars, hashtags from topics)
- [ ] `src/publisher/instagram.py`: `InstagramClient` — create media container → poll for FINISHED → publish → get permalink
- [ ] `src/publisher/publisher.py`: `publish_approved(approved_post, db, config)` — full flow with retry (3× backoff), `already_posted=1` idempotency guard
- [ ] Wire `InstagramApprovalHook` into Telegram callback handler
- [ ] Token rotation reminder: Telegram alert if token expires within 14 days

### Exit Criteria
- Test post appears on Instagram (sandbox if available)
- `posts` row created with `status='published'` and real permalink
- `repos_seen.already_posted=1` set after publish

---

## Step 7 — APScheduler Orchestrator
**Phase:** 3
**Depends on:** Step 6

### Task List
- [ ] `src/main.py`: APScheduler with `run_discovery_pipeline` at 06:00 daily, `expire_stale_evaluations` at 05:45, `check_token_expiry` interval
- [ ] Background thread for Telegram bot polling
- [ ] Daily Telegram summary: scanned / evaluated / sent / approved / posted / errors
- [ ] `python -m src serve` starts daemon (bot + scheduler)

---

## Step 8 — Deployment Hardening
**Phase:** 3
**Depends on:** Step 7

### Task List
- [ ] Startup validation: ping all external APIs before starting scheduler
- [ ] `PRAGMA integrity_check` on DB startup
- [ ] `systemd/reporadar.service` unit file
- [ ] `Makefile`: `install`, `run`, `test`, `logs`
- [ ] `python -m src stats`: 7-day run summary with API call counts and estimated costs
- [ ] Prod README: setup guide covering all prerequisites

---

## Phase & Step Summary

### Phase 1 — Validate the signal ✅ COMPLETE

| Step | What | Status |
|------|------|--------|
| 1 | Scaffold, models, schema, config | ✅ Done |
| 2A | Star velocity scanner | ✅ Done |
| 3 | Gemini evaluation agent | ✅ Done |
| 3B | Local web dashboard | ✅ Done |

**Gate:** Run scanner + evaluate daily for a few days. Confirm repos are genuinely interesting and summaries are publication-ready before starting Phase 2.

### Phase 2 — Human review loop

| Step | What | Status |
|------|------|--------|
| 4 | Telegram digest + approve/reject bot | ⏳ Next |

**Gate:** Run a week of real digests. Confirm approval rate >50% and reviewing takes <2 min/day.

### Phase 3 — Publishing

| Step | What | Status |
|------|------|--------|
| 0 | External account provisioning | ⏳ Parallel with 5–6 |
| 5 | Pillow image card generator | ⏳ Not started |
| 6 | Instagram publisher + image hosting | ⏳ Not started |
| 7 | APScheduler orchestrator | ⏳ Not started |
| 8 | Deployment hardening | ⏳ Not started |

**Fastest path from here:** ~1 weekend for Phase 2, ~2 weekends for Phase 3.

---

## Risk Register

| Risk | Step | Mitigation |
|------|------|------------|
| Signal is noisy — scanner finds boring repos | 2A | Phase 1 gate validates before building anything else |
| Gemini summaries are flat / generic | 3 | Iterate on `SYSTEM_PROMPT` in `src/evaluator/prompts.py` before Phase 2 |
| Gemini 20/day limit hit before useful output | 3 | `gemini_daily_limit` budget guard in `batch.py`; only runs if budget remains |
| `pushed:>` query returns mega-popular repos | 2A | `created:>{max_age_cutoff}` guard added; `REPO_MAX_AGE_DAYS=365` |
| GitHub rate limit exhaustion | 2A | Delta-based scan, search pre-filter, abort if <500 remaining |
| Instagram app review delay | 0 | Start review as soon as Phase 2 validates |
| Instagram rejects local image path | 6 | R2/S3 upload required; covered in Step 0 + Step 6 |
| Same repo posted twice | 6 | `already_posted` flag + UNIQUE constraint on `posts.repo_id` |
| Instagram token expiry (60 days) | 8 | Startup check + Telegram rotation alert |

---

## Key Files Reference

| File | Purpose | Status |
|------|---------|--------|
| `src/models.py` | Pydantic data contracts | ✅ |
| `src/db.py` | SQLite connection, helpers | ✅ |
| `src/config.py` | Env var loader + validation | ✅ |
| `src/scanner/scanner.py` | Star velocity scanner | ✅ |
| `src/evaluator/evaluator.py` | Gemini evaluation agent | ✅ |
| `src/evaluator/batch.py` | Batch runner + budget guard | ✅ |
| `src/web/app.py` | Flask dashboard + scan endpoint | ✅ |
| `src/web/queries.py` | Dashboard DB queries | ✅ |
| `src/cli.py` | CLI: scan / evaluate / serve | ✅ |
| `src/digest/bot.py` | Telegram bot + approval handler | ⏳ Step 4 |
| `src/cards/renderer.py` | Pillow card generator | ⏳ Step 5 |
| `src/publisher/publisher.py` | Instagram publish flow | ⏳ Step 6 |
| `src/main.py` | Daemon entrypoint + scheduler | ⏳ Step 7 |
