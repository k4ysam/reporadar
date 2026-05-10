from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.config import Settings
from src.llm.provider import ClaudeProvider, GeminiProvider, OpenAIProvider, get_provider


def _seed_run(db, run_id):
    db.execute(
        "INSERT INTO pipeline_runs (run_id, started_at, status) VALUES (?, '2026-05-01', 'running')",
        (run_id,),
    )
    db.commit()


def test_get_provider_returns_gemini(tmp_db, mock_run_id):
    _seed_run(tmp_db, mock_run_id)
    settings = Settings(
        gh_token="x", gemini_api_key="AIza", openai_api_key="sk-test", llm_provider="gemini"
    )
    with patch("google.generativeai.configure") as cfg:
        provider = get_provider(settings, tmp_db, mock_run_id)
    assert isinstance(provider, GeminiProvider)
    assert provider.name == "gemini"
    cfg.assert_called_once()


def test_get_provider_returns_claude(tmp_db, mock_run_id):
    _seed_run(tmp_db, mock_run_id)
    settings = Settings(
        gh_token="x", anthropic_api_key="sk-ant-x", openai_api_key="sk-test", llm_provider="claude"
    )
    with patch("anthropic.Anthropic") as anth:
        provider = get_provider(settings, tmp_db, mock_run_id)
    assert isinstance(provider, ClaudeProvider)
    assert provider.name == "claude"
    anth.assert_called_once_with(api_key="sk-ant-x")


def test_get_provider_returns_openai(tmp_db, mock_run_id, monkeypatch):
    _seed_run(tmp_db, mock_run_id)
    settings = Settings(
        gh_token="x", openai_api_key="sk-test", llm_provider="openai"
    )
    openai_cls = MagicMock()
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=openai_cls))

    provider = get_provider(settings, tmp_db, mock_run_id)

    assert isinstance(provider, OpenAIProvider)
    assert provider.name == "openai"
    openai_cls.assert_called_once_with(api_key="sk-test")


def test_claude_provider_logs_api_call(tmp_db, mock_run_id):
    _seed_run(tmp_db, mock_run_id)
    settings = Settings(
        gh_token="x", anthropic_api_key="sk-ant-x", openai_api_key="sk-test", llm_provider="claude"
    )
    with patch("anthropic.Anthropic") as anth_cls:
        client_mock = MagicMock()
        msg = MagicMock()
        block = MagicMock()
        block.type = "text"
        block.text = "hello"
        msg.content = [block]
        client_mock.messages.create.return_value = msg
        anth_cls.return_value = client_mock

        provider = ClaudeProvider(tmp_db, mock_run_id, "sk-ant-x", "claude-sonnet-4-6")
        result = provider.generate("Hi", system="be brief")

    assert result == "hello"
    row = tmp_db.execute(
        "SELECT service, endpoint, status_code FROM api_calls WHERE service='claude'"
    ).fetchone()
    assert row["service"] == "claude"
    assert row["status_code"] == 200


def test_gemini_provider_logs_api_call(tmp_db, mock_run_id):
    _seed_run(tmp_db, mock_run_id)
    with patch("google.generativeai.configure"), patch("google.generativeai.GenerativeModel") as model_cls:
        model = MagicMock()
        resp = MagicMock()
        resp.text = "hi"
        model.generate_content.return_value = resp
        model_cls.return_value = model

        provider = GeminiProvider(tmp_db, mock_run_id, "AIza", "gemini-2.0-flash")
        result = provider.generate("Hi", system="be brief")

    assert result == "hi"
    row = tmp_db.execute(
        "SELECT service FROM api_calls WHERE service='gemini'"
    ).fetchone()
    assert row["service"] == "gemini"


def test_openai_provider_logs_api_call(tmp_db, mock_run_id, monkeypatch):
    _seed_run(tmp_db, mock_run_id)
    client_mock = MagicMock()
    resp = SimpleNamespace(output_text="hello")
    client_mock.responses.create.return_value = resp
    openai_cls = MagicMock(return_value=client_mock)
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=openai_cls))

    provider = OpenAIProvider(tmp_db, mock_run_id, "sk-test", "gpt-5.4-mini")
    result = provider.generate("Hi", system="be brief")

    assert result == "hello"
    client_mock.responses.create.assert_called_once_with(
        model="gpt-5.4-mini",
        input="Hi",
        max_output_tokens=1024,
        instructions="be brief",
    )
    row = tmp_db.execute(
        "SELECT service, endpoint, status_code FROM api_calls WHERE service='openai'"
    ).fetchone()
    assert row["service"] == "openai"
    assert row["endpoint"] == "responses.create"
    assert row["status_code"] == 200
