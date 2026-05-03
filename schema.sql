CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id       TEXT PRIMARY KEY,
    started_at   TEXT NOT NULL,
    completed_at TEXT,
    status       TEXT NOT NULL CHECK(status IN ('running', 'completed', 'failed')),
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS repos_seen (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name               TEXT NOT NULL UNIQUE,
    github_repo_id          INTEGER UNIQUE,
    first_seen_at           TEXT NOT NULL,
    last_scan_at            TEXT NOT NULL,
    star_count_at_last_scan INTEGER NOT NULL DEFAULT 0,
    excluded_until          TEXT,
    already_posted          INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS evaluations (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id               INTEGER NOT NULL REFERENCES repos_seen(id),
    run_id                TEXT REFERENCES pipeline_runs(run_id),
    evaluated_at          TEXT NOT NULL,
    summary               TEXT,
    why_interesting       TEXT,
    audience              TEXT,
    novelty_score         REAL,
    explainability_score  REAL,
    overall_score         REAL,
    growth_pct            REAL,
    approved              INTEGER,
    telegram_message_id   INTEGER,
    reviewed_at           TEXT,
    auto_expired          INTEGER NOT NULL DEFAULT 0,
    claude_raw_response   TEXT
);

CREATE TABLE IF NOT EXISTS posts (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    evaluation_id        INTEGER UNIQUE REFERENCES evaluations(id),
    repo_id              INTEGER UNIQUE REFERENCES repos_seen(id),
    card_path            TEXT,
    caption              TEXT,
    image_host_url       TEXT,
    instagram_media_id   TEXT,
    instagram_permalink  TEXT,
    status               TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'published', 'failed')),
    retry_count          INTEGER NOT NULL DEFAULT 0,
    error_message        TEXT,
    published_at         TEXT,
    run_id               TEXT REFERENCES pipeline_runs(run_id)
);

CREATE TABLE IF NOT EXISTS api_calls (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      TEXT REFERENCES pipeline_runs(run_id),
    service     TEXT NOT NULL,
    endpoint    TEXT NOT NULL,
    status_code INTEGER,
    latency_ms  INTEGER,
    called_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_repos_seen_full_name    ON repos_seen(full_name);
CREATE INDEX IF NOT EXISTS idx_evaluations_run_id      ON evaluations(run_id);
CREATE INDEX IF NOT EXISTS idx_evaluations_approved    ON evaluations(approved);
CREATE INDEX IF NOT EXISTS idx_evaluations_repo_id     ON evaluations(repo_id);
CREATE INDEX IF NOT EXISTS idx_api_calls_run_id        ON api_calls(run_id);
