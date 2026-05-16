from __future__ import annotations

import psycopg

from src.ai_gateway.images.openai_image import OpenAIImageClient
from src.ai_gateway.llm.base import LLMProvider
from src.ai_gateway.llm.claude import ClaudeProvider
from src.ai_gateway.llm.gemini import GeminiProvider
from src.ai_gateway.llm.openai import OpenAIProvider
from src.common.config import Settings


def get_llm_provider(settings: Settings, conn: psycopg.Connection, run_id: str) -> LLMProvider:
    if settings.llm_provider == "claude":
        return ClaudeProvider(conn, run_id, settings.anthropic_api_key, settings.claude_model)
    if settings.llm_provider == "gemini":
        return GeminiProvider(conn, run_id, settings.gemini_api_key, settings.gemini_model)
    if settings.llm_provider == "openai":
        return OpenAIProvider(conn, run_id, settings.openai_api_key, settings.openai_model)
    raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")


def get_image_provider(
    settings: Settings,
    conn: psycopg.Connection,
    run_id: str,
    *,
    size: str = "1024x1024",
) -> OpenAIImageClient:
    return OpenAIImageClient(conn, run_id, settings.openai_api_key, size=size)
