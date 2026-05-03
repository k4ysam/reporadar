import sqlite3

import pytest

from src.db import get_db, init_db, log_api_call


def test_init_db_creates_tables(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert {"pipeline_runs", "repos_seen", "evaluations", "posts", "api_calls"} <= tables
    conn.close()


def test_init_db_idempotent(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    init_db(db_path)  # second call must not raise


def test_repos_seen_unique_constraint(tmp_db):
    now = "2026-05-01T00:00:00"
    tmp_db.execute(
        "INSERT INTO repos_seen (full_name, first_seen_at, last_scan_at) VALUES (?, ?, ?)",
        ("owner/repo", now, now),
    )
    tmp_db.commit()
    with pytest.raises(sqlite3.IntegrityError):
        tmp_db.execute(
            "INSERT INTO repos_seen (full_name, first_seen_at, last_scan_at) VALUES (?, ?, ?)",
            ("owner/repo", now, now),
        )
        tmp_db.commit()


def test_posts_repo_id_unique_constraint(tmp_db):
    now = "2026-05-01T00:00:00"
    tmp_db.execute(
        "INSERT INTO repos_seen (full_name, first_seen_at, last_scan_at) VALUES (?, ?, ?)",
        ("owner/repo", now, now),
    )
    tmp_db.commit()
    repo_id = tmp_db.execute("SELECT id FROM repos_seen WHERE full_name='owner/repo'").fetchone()[0]
    tmp_db.execute("INSERT INTO posts (repo_id, status) VALUES (?, 'pending')", (repo_id,))
    tmp_db.commit()
    with pytest.raises(sqlite3.IntegrityError):
        tmp_db.execute("INSERT INTO posts (repo_id, status) VALUES (?, 'pending')", (repo_id,))
        tmp_db.commit()


def test_foreign_keys_enforced(tmp_db):
    with pytest.raises(sqlite3.IntegrityError):
        tmp_db.execute(
            "INSERT INTO evaluations (repo_id, evaluated_at) VALUES (999, '2026-05-01T00:00:00')"
        )
        tmp_db.commit()


def test_log_api_call(tmp_db, mock_run_id):
    tmp_db.execute(
        "INSERT INTO pipeline_runs (run_id, started_at, status) VALUES (?, '2026-05-01T00:00:00', 'running')",
        (mock_run_id,),
    )
    tmp_db.commit()
    log_api_call(tmp_db, mock_run_id, "github", "/rate_limit", 200, 42)
    row = tmp_db.execute("SELECT * FROM api_calls WHERE run_id=?", (mock_run_id,)).fetchone()
    assert row["service"] == "github"
    assert row["status_code"] == 200
    assert row["latency_ms"] == 42
