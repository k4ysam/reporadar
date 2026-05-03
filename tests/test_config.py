import os

import pytest

from src.config import Settings


def test_missing_gh_token_raises(monkeypatch):
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    with pytest.raises(RuntimeError, match="GH_TOKEN"):
        Settings.from_env()


def test_missing_anthropic_key_raises(monkeypatch):
    monkeypatch.setenv("GH_TOKEN", "ghp_test")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        Settings.from_env()


def test_defaults_applied(monkeypatch):
    monkeypatch.setenv("GH_TOKEN", "ghp_test")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.delenv("MAX_CANDIDATES_PER_RUN", raising=False)
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
    s = Settings.from_env()
    assert s.max_candidates_per_run == 15
    assert s.anthropic_model == "claude-sonnet-4-6"


def test_numeric_coercion(monkeypatch):
    monkeypatch.setenv("GH_TOKEN", "ghp_test")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("MAX_CANDIDATES_PER_RUN", "7")
    monkeypatch.setenv("STAR_GROWTH_MIN_PCT", "150.5")
    s = Settings.from_env()
    assert s.max_candidates_per_run == 7
    assert s.star_growth_min_pct == 150.5
