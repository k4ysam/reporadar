from __future__ import annotations

import time

import psycopg

from src.ai_gateway.llm.base import _BaseProvider


class ClaudeProvider(_BaseProvider):
    name = "claude"

    def __init__(self, conn: psycopg.Connection, run_id: str, api_key: str, model: str):
        super().__init__(conn, run_id)
        from anthropic import Anthropic

        self._client = Anthropic(api_key=api_key)
        self.model = model

    def generate(self, prompt: str, system: str | None = None) -> str:
        t0 = time.monotonic()
        kwargs: dict = {
            "model": self.model,
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

        text_blocks = [b.text for b in resp.content if getattr(b, "type", None) == "text"]
        return "".join(text_blocks).strip()
