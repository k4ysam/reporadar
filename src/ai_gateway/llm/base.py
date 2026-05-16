from __future__ import annotations

import time
from typing import Protocol

import psycopg

from src.common.db import log_api_call


class LLMProvider(Protocol):
    name: str
    model: str

    def generate(self, prompt: str, system: str | None = None) -> str: ...


class _BaseProvider:
    name: str = "base"
    model: str = ""

    def __init__(self, conn: psycopg.Connection, run_id: str):
        self._conn = conn
        self._run_id = run_id

    def _log_call(self, endpoint: str, status_code: int, started_at: float) -> None:
        latency_ms = int((time.monotonic() - started_at) * 1000)
        try:
            log_api_call(self._conn, self._run_id, self.name, endpoint, status_code, latency_ms)
        except Exception:
            # Observability must never crash the caller.
            pass
