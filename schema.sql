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

CREATE TABLE IF NOT EXISTS hackathon_projects (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    devpost_url       TEXT NOT NULL UNIQUE,
    project_name      TEXT NOT NULL,
    tagline           TEXT,
    hackathon_name    TEXT,
    prize             TEXT,
    team              TEXT,
    github_url        TEXT,
    demo_url          TEXT,
    submitted_at      TEXT,
    first_seen_at     TEXT NOT NULL,
    last_scan_at      TEXT NOT NULL,
    excluded_until    TEXT,
    already_posted    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS evaluations (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    content_type          TEXT NOT NULL DEFAULT 'repo' CHECK(content_type IN ('repo', 'hackathon')),
    repo_id               INTEGER REFERENCES repos_seen(id),
    hackathon_id          INTEGER REFERENCES hackathon_projects(id),
    run_id                TEXT REFERENCES pipeline_runs(run_id),
    evaluated_at          TEXT NOT NULL,
    summary               TEXT,
    why_interesting       TEXT,
    audience              TEXT,
    novelty_score         REAL,
    explainability_score  REAL,
    overall_score         REAL,
    skip                  INTEGER NOT NULL DEFAULT 0,
    growth_pct            REAL,
    raw_response          TEXT,
    llm_provider          TEXT,
    -- legacy columns retained for compatibility with existing rows --
    approved              INTEGER,
    telegram_message_id   INTEGER,
    reviewed_at           TEXT,
    auto_expired          INTEGER NOT NULL DEFAULT 0,
    claude_raw_response   TEXT
);

CREATE TABLE IF NOT EXISTS posts (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    evaluation_id        INTEGER UNIQUE REFERENCES evaluations(id),
    content_type         TEXT NOT NULL DEFAULT 'repo' CHECK(content_type IN ('repo', 'hackathon')),
    media_type           TEXT NOT NULL DEFAULT 'single' CHECK(media_type IN ('single', 'carousel')),
    repo_id              INTEGER UNIQUE REFERENCES repos_seen(id),
    hackathon_id         INTEGER UNIQUE REFERENCES hackathon_projects(id),
    card_paths           TEXT,                  -- JSON array of local image paths
    image_host_urls      TEXT,                  -- JSON array of public URLs
    caption              TEXT,
    instagram_media_id   TEXT,
    instagram_permalink  TEXT,
    status               TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'rendered', 'uploaded', 'published', 'failed')),
    retry_count          INTEGER NOT NULL DEFAULT 0,
    error_message        TEXT,
    scheduled_for        TEXT,
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

CREATE INDEX IF NOT EXISTS idx_repos_seen_full_name       ON repos_seen(full_name);
CREATE INDEX IF NOT EXISTS idx_hackathon_devpost_url      ON hackathon_projects(devpost_url);
CREATE INDEX IF NOT EXISTS idx_evaluations_run_id         ON evaluations(run_id);
CREATE INDEX IF NOT EXISTS idx_evaluations_repo_id        ON evaluations(repo_id);
CREATE INDEX IF NOT EXISTS idx_evaluations_hackathon_id   ON evaluations(hackathon_id);
CREATE INDEX IF NOT EXISTS idx_evaluations_content_type   ON evaluations(content_type);
CREATE INDEX IF NOT EXISTS idx_posts_status               ON posts(status);
CREATE INDEX IF NOT EXISTS idx_posts_scheduled_for        ON posts(scheduled_for);
CREATE INDEX IF NOT EXISTS idx_api_calls_run_id           ON api_calls(run_id);
CREATE INDEX IF NOT EXISTS idx_api_calls_service_date     ON api_calls(service, called_at);
