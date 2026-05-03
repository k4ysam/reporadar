from __future__ import annotations

import sqlite3
from pathlib import Path


def get_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db(db_path: str) -> None:
    schema_path = Path(__file__).parent.parent / "schema.sql"
    sql = schema_path.read_text(encoding="utf-8")
    conn = get_db(db_path)
    with conn:
        conn.executescript(sql)
    conn.close()


def get_app_setting(conn: sqlite3.Connection, key: str, default: str | None = None) -> str | None:
    row = conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
    return row[0] if row else default


def set_app_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)",
        (key, value),
    )
    conn.commit()


def log_api_call(
    conn: sqlite3.Connection,
    run_id: str,
    service: str,
    endpoint: str,
    status_code: int | None,
    latency_ms: int,
) -> None:
    from datetime import datetime, timezone

    conn.execute(
        """
        INSERT INTO api_calls (run_id, service, endpoint, status_code, latency_ms, called_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (run_id, service, endpoint, status_code, latency_ms, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
