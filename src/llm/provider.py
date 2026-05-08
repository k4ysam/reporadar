from __future__ import annotations

import sqlite3
import time
from typing import Protocol

from src.config import Settings
from src.db import log_api_call


class LLMProvider(Protocol):
    name: str

    def generate(self, prompt: str, system: str | None = None) -> str: ...


class _BaseProvider:
    name: str = "base"

    def __init__(self, db: sqlite3.Connection, run_id: str):
        self._db = db
        self._run_id = run_id

    def _log_call(self, endpoint: str, status_code: int, started_at: float) -> None:
        latency_ms = int((time.monotonic() - started_at) * 1000)
        log_api_call(self._db, self._run_id, self.name, endpoint, status_code, latency_ms)


class ClaudeProvider(_BaseProvider):
    name = "claude"

    def __init__(self, db: sqlite3.Connection, run_id: str, api_key: str, model: str):
        super().__init__(db, run_id)
        from anthropic import Anthropic

        self._client = Anthropic(api_key=api_key)
        self._model = model

    def generate(self, prompt: str, system: str | None = None) -> str:
        t0 = time.monotonic()
        kwargs: dict = {
            "model": self._model,
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        try:
            resp = self._client.messages.create(**kwargs)
            self._log_call("messages.create", 200, t0)
        except Exception:
            self._log_call("messages.create", 500, t0)
            raise
        # Anthropic returns content blocks
        text_blocks = [b.text for b in resp.content if getattr(b, "type", None) == "text"]
        return "".join(text_blocks).strip()


class GeminiProvider(_BaseProvider):
    name = "gemini"

    def __init__(self, db: sqlite3.Connection, run_id: str, api_key: str, model: str):
        super().__init__(db, run_id)
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        self._genai = genai
        self._model_name = model

    def generate(self, prompt: str, system: str | None = None) -> str:
        model = self._genai.GenerativeModel(
            model_name=self._model_name,
            system_instruction=system,
        )
        t0 = time.monotonic()
        try:
            resp = model.generate_content(prompt)
            self._log_call("generate_content", 200, t0)
        except Exception:
            self._log_call("generate_content", 500, t0)
            raise
        return (resp.text or "").strip()


def get_provider(settings: Settings, db: sqlite3.Connection, run_id: str) -> LLMProvider:
    if settings.llm_provider == "claude":
        return ClaudeProvider(db, run_id, settings.anthropic_api_key, settings.claude_model)
    if settings.llm_provider == "gemini":
        return GeminiProvider(db, run_id, settings.gemini_api_key, settings.gemini_model)
    raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")
