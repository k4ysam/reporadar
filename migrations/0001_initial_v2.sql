-- RepoRadar v2 initial schema (Postgres / Supabase)
--
-- Two domain tables per Doc/reporadar_database_design.md:
--   * candidate_repository_evaluations — working pipeline data
--   * posted_repositories              — permanent posting archive
--
-- Plus two operational tables that every service writes to:
--   * pipeline_runs  — orchestrator run tracking
--   * api_calls      — observability for LLM / GitHub / Devpost calls
--
-- Idempotent: every CREATE uses IF NOT EXISTS. Safe to re-run.

-- ----------------------------------------------------------------------------
-- pipeline_runs (orchestrator)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id        TEXT PRIMARY KEY,
    started_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at  TIMESTAMPTZ,
    status        TEXT NOT NULL DEFAULT 'running'
                  CHECK (status IN ('running', 'completed', 'failed')),
    error_message TEXT,
    requested_by  TEXT,
    run_type      TEXT NOT NULL DEFAULT 'daily_discovery',
    config        JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_started_at
    ON pipeline_runs (started_at DESC);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status
    ON pipeline_runs (status);

-- ----------------------------------------------------------------------------
-- api_calls (shared observability)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS api_calls (
    id          BIGSERIAL PRIMARY KEY,
    run_id      TEXT REFERENCES pipeline_runs (run_id) ON DELETE SET NULL,
    service     TEXT NOT NULL,
    endpoint    TEXT NOT NULL,
    status_code INTEGER,
    latency_ms  INTEGER,
    called_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_api_calls_run_id
    ON api_calls (run_id);
CREATE INDEX IF NOT EXISTS idx_api_calls_service_called_at
    ON api_calls (service, called_at DESC);

-- ----------------------------------------------------------------------------
-- candidate_repository_evaluations
--
-- One row per (run_id, canonical_repo_key). Each row represents one candidate
-- inside one discovery run. Section payloads are JSONB so individual services
-- can evolve their own data shape without schema migrations.
--
-- Section ownership (per Doc §12):
--   source            — Discovery
--   discovery         — Discovery
--   github / hackathon — Enrichment
--   enrichment        — Enrichment
--   deduplication     — Project Registry / Deduplication
--   evaluation        — Evaluation
--   ranking           — Selection / Ranking
--   selection         — Selection
--   post_link         — Publishing / Packaging
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS candidate_repository_evaluations (
    id                  TEXT PRIMARY KEY,
    run_id              TEXT NOT NULL REFERENCES pipeline_runs (run_id) ON DELETE CASCADE,
    project_id          TEXT NOT NULL,
    canonical_repo_key  TEXT NOT NULL,
    source_type         TEXT NOT NULL
                        CHECK (source_type IN ('github_discovery', 'devpost_discovery', 'manual_submission')),
    status              TEXT NOT NULL DEFAULT 'discovered'
                        CHECK (status IN (
                            'discovered', 'enriched', 'evaluation_pending', 'evaluated',
                            'skipped', 'ranked', 'selected', 'post_generation_requested',
                            'posted', 'rejected', 'failed', 'archived'
                        )),

    -- Service-owned JSONB sections (all optional except source)
    source              JSONB NOT NULL DEFAULT '{}'::jsonb,
    discovery           JSONB NOT NULL DEFAULT '{}'::jsonb,
    github              JSONB,
    hackathon           JSONB,
    enrichment          JSONB NOT NULL DEFAULT '{}'::jsonb,
    deduplication       JSONB NOT NULL DEFAULT '{}'::jsonb,
    evaluation          JSONB,
    ranking             JSONB,
    selection           JSONB,
    post_link           JSONB,
    audit               JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (run_id, canonical_repo_key)
);

CREATE INDEX IF NOT EXISTS idx_cand_run_id
    ON candidate_repository_evaluations (run_id);
CREATE INDEX IF NOT EXISTS idx_cand_project_id
    ON candidate_repository_evaluations (project_id);
CREATE INDEX IF NOT EXISTS idx_cand_canonical_repo_key
    ON candidate_repository_evaluations (canonical_repo_key);
CREATE INDEX IF NOT EXISTS idx_cand_status
    ON candidate_repository_evaluations (status);
CREATE INDEX IF NOT EXISTS idx_cand_source_type
    ON candidate_repository_evaluations (source_type);

-- Most important ranking query: top candidates per run, by ranking score,
-- skip=false, already_posted=false.
CREATE INDEX IF NOT EXISTS idx_cand_run_score
    ON candidate_repository_evaluations
       (run_id, ((ranking ->> 'ranking_score')::numeric) DESC);
CREATE INDEX IF NOT EXISTS idx_cand_eval_skip
    ON candidate_repository_evaluations (((evaluation ->> 'skip')::boolean));
CREATE INDEX IF NOT EXISTS idx_cand_already_posted
    ON candidate_repository_evaluations (((deduplication ->> 'already_posted')::boolean));

-- ----------------------------------------------------------------------------
-- posted_repositories
--
-- One row per canonical project that has been posted, exported, or marked
-- manually posted. This is the permanent historical archive — when a project
-- is selected for posting, copy the relevant snapshots in.
--
-- Each row may contain multiple post_instances (one per channel).
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS posted_repositories (
    id                   TEXT PRIMARY KEY,
    project_id           TEXT NOT NULL,
    canonical_repo_key   TEXT NOT NULL UNIQUE,
    canonical_repo_url   TEXT NOT NULL,

    github               JSONB,
    hackathon            JSONB,
    project_description  JSONB NOT NULL DEFAULT '{}'::jsonb,
    source               JSONB NOT NULL DEFAULT '{}'::jsonb,
    evaluation_snapshot  JSONB NOT NULL DEFAULT '{}'::jsonb,
    ranking_snapshot     JSONB NOT NULL DEFAULT '{}'::jsonb,
    post_instances       JSONB NOT NULL DEFAULT '[]'::jsonb,
    posting_state        JSONB NOT NULL DEFAULT '{"has_been_posted": false, "do_not_repost": false}'::jsonb,
    audit                JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_posted_project_id
    ON posted_repositories (project_id);
CREATE INDEX IF NOT EXISTS idx_posted_canonical_url
    ON posted_repositories (canonical_repo_url);
CREATE INDEX IF NOT EXISTS idx_posted_has_been_posted
    ON posted_repositories (((posting_state ->> 'has_been_posted')::boolean));
CREATE INDEX IF NOT EXISTS idx_posted_first_posted_at
    ON posted_repositories (((posting_state ->> 'first_posted_at')));

-- ----------------------------------------------------------------------------
-- Auto-update updated_at trigger
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_cand_updated_at ON candidate_repository_evaluations;
CREATE TRIGGER trg_cand_updated_at
    BEFORE UPDATE ON candidate_repository_evaluations
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_posted_updated_at ON posted_repositories;
CREATE TRIGGER trg_posted_updated_at
    BEFORE UPDATE ON posted_repositories
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ----------------------------------------------------------------------------
-- RLS: defense in depth. RepoRadar's backend connects via the project pooler
-- with a privileged role, so RLS is not used for access control. We still
-- enable it so that any future anon/authenticated role exposure fails closed.
-- ----------------------------------------------------------------------------
ALTER TABLE pipeline_runs                       ENABLE ROW LEVEL SECURITY;
ALTER TABLE api_calls                           ENABLE ROW LEVEL SECURITY;
ALTER TABLE candidate_repository_evaluations    ENABLE ROW LEVEL SECURITY;
ALTER TABLE posted_repositories                 ENABLE ROW LEVEL SECURITY;
