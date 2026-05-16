from __future__ import annotations

import time

import psycopg

from src.ai_gateway.llm.base import _BaseProvider


class OpenAIProvider(_BaseProvider):
    name = "openai"

    def __init__(self, conn: psycopg.Connection, run_id: str, api_key: str, model: str):
        super().__init__(conn, run_id)
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key)
        self.model = model

    def generate(self, prompt: str, system: str | None = None) -> str:
        kwargs: dict = {
            "model": self.model,
            "input": prompt,
            "max_output_tokens": 1024,
        }
        if system:
            kwargs["instructions"] = system

        t0 = time.monotonic()
        try:
            resp = self._client.responses.create(**kwargs)
            self._log_call("responses.create", 200, t0)
        except Exception:
            self._log_call("responses.create", 500, t0)
            raise

        output_text = getattr(resp, "output_text", None)
        if output_text:
            return output_text.strip()

        text_blocks: list[str] = []
        for item in getattr(resp, "output", []) or []:
            for content in getattr(item, "content", []) or []:
                if getattr(content, "type", None) == "output_text":
                    text_blocks.append(getattr(content, "text", ""))
        return "".join(text_blocks).strip()
