"""Shared test fixtures.

The v2 codebase talks to Postgres via psycopg, but most unit tests don't need
a real DB — they exercise pure functions. The `fake_conn` fixture below
provides a minimal stub that mimics psycopg.Connection + cursor behavior just
well enough for code paths that incidentally call `log_api_call` or simple
INSERT/SELECT. Tests that need richer behavior should mock more specifically.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest


class _FakeCursor:
    def __init__(self, store):
        self._store = store
        self._result = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self._store["last_sql"] = sql
        self._store["last_params"] = params

    def fetchone(self):
        return None

    def fetchall(self):
        return []


class FakeConnection:
    """Stand-in for `psycopg.Connection` that records the most recent SQL
    + params and silently swallows everything else. Good enough for code
    paths whose return value doesn't depend on DB state."""

    def __init__(self):
        self._store: dict = {}

    def cursor(self, **kwargs):
        return _FakeCursor(self._store)

    def commit(self):
        pass

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def fake_conn() -> FakeConnection:
    return FakeConnection()


@pytest.fixture
def mock_run_id() -> str:
    return "run_00000000-0000-0000-0000-000000000001"


@pytest.fixture
def fixed_now() -> datetime:
    return datetime(2026, 5, 16, 12, 0, 0, tzinfo=timezone.utc)
