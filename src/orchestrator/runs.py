"""Pipeline run lifecycle — owned exclusively by the orchestrator."""
from __future__ import annotations

from datetime import datetime, timezone

import psycopg

from src.common.ids import run_id as new_run_id


def start_run(
    conn: psycopg.Connection,
    *,
    run_type: str = "daily_discovery",
    requested_by: str = "manual",
    config: dict | None = None,
) -> str:
    rid = new_run_id()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO pipeline_runs (run_id, started_at, status, run_type, requested_by, config)
            VALUES (%s, %s, 'running', %s, %s, %s::jsonb)
            """,
            (
                rid,
                datetime.now(timezone.utc),
                run_type,
                requested_by,
                __import__("json").dumps(config or {}),
            ),
        )
    conn.commit()
    return rid


def finish_run(conn: psycopg.Connection, run_id: str, *, error: str | None = None) -> None:
    if error is None:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE pipeline_runs SET status='completed', completed_at=%s
                WHERE run_id=%s
                """,
                (datetime.now(timezone.utc), run_id),
            )
    else:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE pipeline_runs SET status='failed', completed_at=%s, error_message=%s
                WHERE run_id=%s
                """,
                (datetime.now(timezone.utc), error[:500], run_id),
            )
    conn.commit()
