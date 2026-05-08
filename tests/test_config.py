import os

import pytest

from src.config import Settings


def _clear(monkeypatch):
    for key in (
        "GH_TOKEN", "GEMINI_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY",
        "LLM_PROVIDER", "LLM_MODEL", "GEMINI_MODEL", "CLAUDE_MODEL", "OPENAI_MODEL",
        "MAX_CANDIDATES_PER_RUN", "STAR_GROWTH_MIN_PCT",
    ):
        monkeypatch.delenv(key, raising=False)


def test_missing_gh_token_raises(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "AIza-test")
    with pytest.raises(RuntimeError, match="GH_TOKEN"):
        Settings.from_env()


def test_missing_gemini_key_raises(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("GH_TOKEN", "ghp_test")
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        Settings.from_env()


def test_missing_anthropic_key_raises(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("GH_TOKEN", "ghp_test")
    monkeypatch.setenv("LLM_PROVIDER", "claude")
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        Settings.from_env()


def test_missing_openai_key_raises(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("GH_TOKEN", "ghp_test")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        Settings.from_env()


def test_claude_provider_with_key(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("GH_TOKEN", "ghp_test")
    monkeypatch.setenv("LLM_PROVIDER", "claude")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-x")
    s = Settings.from_env()
    assert s.llm_provider == "claude"
    assert s.anthropic_api_key == "sk-ant-x"


def test_openai_provider_with_key(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("GH_TOKEN", "ghp_test")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    s = Settings.from_env()
    assert s.llm_provider == "openai"
    assert s.openai_api_key == "sk-test"
    assert s.openai_model == "gpt-5.4-mini"
    assert s.llm_model == "gpt-5.4-mini"


def test_invalid_provider_raises(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("GH_TOKEN", "ghp_test")
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    with pytest.raises(RuntimeError, match="LLM_PROVIDER"):
        Settings.from_env()


def test_defaults_applied(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("GH_TOKEN", "ghp_test")
    monkeypatch.setenv("GEMINI_API_KEY", "AIza-test")
    s = Settings.from_env()
    assert s.max_candidates_per_run == 15
    assert s.gemini_model == "gemini-2.0-flash"
    assert s.llm_provider == "gemini"
    assert s.llm_model == "gemini-2.0-flash"  # property derived from provider


def test_numeric_coercion(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("GH_TOKEN", "ghp_test")
    monkeypatch.setenv("GEMINI_API_KEY", "AIza-test")
    monkeypatch.setenv("MAX_CANDIDATES_PER_RUN", "7")
    monkeypatch.setenv("STAR_GROWTH_MIN_PCT", "150.5")
    s = Settings.from_env()
    assert s.max_candidates_per_run == 7
    assert s.star_growth_min_pct == 150.5
