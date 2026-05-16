"""Postgres connection layer (psycopg 3).

All services obtain DB connections through `connect(settings)`. Callers should
use the context manager:

    with connect(settings) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT 1")

## Why `prepare_threshold=None` + `autocommit=True`

We talk to Supabase through the **transaction pooler** (port 6543 in
`DATABASE_URL`). The pooler reuses backend connections across client
transactions, so server-side prepared statements registered on one backend
do not exist on the next — psycopg 3's default of auto-preparing after the
5th identical query produces:

    psycopg.errors.InvalidSqlStatementName: prepared statement "_pg3_N" does not exist

The fix is `prepare_threshold=None`, which disables server-side preparation
entirely. (See Supabase + psycopg notes:
https://www.psycopg.org/psycopg3/docs/api/connections.html#psycopg.Connection.prepare_threshold )

We also set `autocommit=True` so that a failed statement doesn't leave the
connection stuck in `INTRANS_ERROR`, which would block every subsequent
write (including the orchestrator's `finish_run`) with:

    psycopg.errors.InFailedSqlTransaction: current transaction is aborted

Every repository helper in this codebase does single-statement writes
followed by `conn.commit()` — `autocommit=True` makes the explicit commits
no-ops (psycopg silently ignores `commit()` in autocommit mode) and removes
the cross-statement transaction failure mode entirely. If a multi-statement
atomic group is needed later, wrap it with `with conn.transaction():`.
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator

import psycopg
from psycopg.rows import dict_row

from src.common.config import Settings


def _connect_raw(settings: Settings) -> psycopg.Connection:
    return psycopg.connect(
        settings.database_url,
        autocommit=True,
        prepare_threshold=None,
    )


@contextmanager
def connect(settings: Settings) -> Iterator[psycopg.Connection]:
    """Yield a new Postgres connection configured for the Supabase pooler."""
    conn = _connect_raw(settings)
    try:
        yield conn
    finally:
        conn.close()


def open_connection(settings: Settings) -> psycopg.Connection:
    """Return a new Postgres connection. Caller must call .close() when done.

    Used by the Flask dashboard where the request handler manages connection
    lifetime explicitly (one connection per HTTP request).
    """
    return _connect_raw(settings)


def log_api_call(
    conn: psycopg.Connection,
    run_id: str | None,
    service: str,
    endpoint: str,
    status_code: int | None,
    latency_ms: int,
) -> None:
    """Insert one row into api_calls. Swallows its own errors.

    Observability must never crash the caller — if logging fails (DB down,
    schema not applied, transient pooler error), the pipeline keeps running.
    """
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO api_calls (run_id, service, endpoint, status_code, latency_ms, called_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    run_id,
                    service,
                    endpoint,
                    status_code,
                    latency_ms,
                    datetime.now(timezone.utc),
                ),
            )
    except Exception:
        pass


class TimedCall:
    """Tiny helper for instrumenting external HTTP / LLM calls.

    Usage:
        with TimedCall(conn, run_id, "github", "/search/repositories") as t:
            resp = http_get(...)
            t.status_code = resp.status_code
    """

    def __init__(self, conn: psycopg.Connection, run_id: str | None, service: str, endpoint: str):
        self._conn = conn
        self._run_id = run_id
        self._service = service
        self._endpoint = endpoint
        self.status_code: int | None = None
        self._t0 = 0.0

    def __enter__(self) -> "TimedCall":
        self._t0 = time.monotonic()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        latency_ms = int((time.monotonic() - self._t0) * 1000)
        log_api_call(
            self._conn,
            self._run_id,
            self._service,
            self._endpoint,
            self.status_code if exc is None else (self.status_code or 500),
            latency_ms,
        )


def dict_cursor(conn: psycopg.Connection):
    """Shortcut: open a cursor that returns rows as dicts."""
    return conn.cursor(row_factory=dict_row)
