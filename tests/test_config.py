import os

import pytest

from src.config import Settings


def test_missing_gh_token_raises(monkeypatch):
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "AIza-test")
    with pytest.raises(RuntimeError, match="GH_TOKEN"):
        Settings.from_env()


def test_missing_gemini_key_raises(monkeypatch):
    monkeypatch.setenv("GH_TOKEN", "ghp_test")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        Settings.from_env()


def test_defaults_applied(monkeypatch):
    monkeypatch.setenv("GH_TOKEN", "ghp_test")
    monkeypatch.setenv("GEMINI_API_KEY", "AIza-test")
    monkeypatch.delenv("MAX_CANDIDATES_PER_RUN", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    s = Settings.from_env()
    assert s.max_candidates_per_run == 15
    assert s.llm_model == "gemini-2.0-flash"


def test_numeric_coercion(monkeypatch):
    monkeypatch.setenv("GH_TOKEN", "ghp_test")
    monkeypatch.setenv("GEMINI_API_KEY", "AIza-test")
    monkeypatch.setenv("MAX_CANDIDATES_PER_RUN", "7")
    monkeypatch.setenv("STAR_GROWTH_MIN_PCT", "150.5")
    s = Settings.from_env()
    assert s.max_candidates_per_run == 7
    assert s.star_growth_min_pct == 150.5
