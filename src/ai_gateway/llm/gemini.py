from __future__ import annotations

import time

import psycopg

from src.ai_gateway.llm.base import _BaseProvider


class GeminiProvider(_BaseProvider):
    name = "gemini"

    def __init__(self, conn: psycopg.Connection, run_id: str, api_key: str, model: str):
        super().__init__(conn, run_id)
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        self._genai = genai
        self.model = model

    def generate(self, prompt: str, system: str | None = None) -> str:
        model = self._genai.GenerativeModel(
            model_name=self.model,
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
