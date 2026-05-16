"""LLM JSON output parser. Handles fenced + retry-on-malformed cases."""
from __future__ import annotations

import json
import re

from src.ai_gateway.llm.base import LLMProvider


def parse_evaluation_json(text: str) -> dict:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return json.loads(cleaned.strip())


def call_with_retry(provider: LLMProvider, prompt: str, system: str) -> tuple[dict, str]:
    raw = provider.generate(prompt, system=system)
    try:
        return parse_evaluation_json(raw), raw
    except (json.JSONDecodeError, ValueError):
        retry = f"{prompt}\n\nReturn ONLY valid JSON. No explanation, no markdown."
        raw = provider.generate(retry, system=system)
        return parse_evaluation_json(raw), raw
