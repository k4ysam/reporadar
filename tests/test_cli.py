from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import responses as resp_mock

from src.cli import cmd_verify_env
from src.config import Settings


@resp_mock.activate
def test_verify_env_uses_persisted_run_id_for_api_logging(tmp_db):
    settings = Settings(gh_token="ghp_test", gemini_api_key="AIza-test")
    resp_mock.add(
        resp_mock.GET,
        "https://api.github.com/rate_limit",
        json={"resources": {"core": {"remaining": 4999}}},
    )
    provider = SimpleNamespace(name="gemini", generate=lambda prompt, system=None: "OK")

    with patch("src.llm.provider.get_provider", return_value=provider):
        result = cmd_verify_env(None, settings, tmp_db)

    assert result == 0
    api_call = tmp_db.execute(
        "SELECT run_id, service FROM api_calls WHERE service='github'"
    ).fetchone()
    assert api_call["service"] == "github"
    run = tmp_db.execute(
        "SELECT status FROM pipeline_runs WHERE run_id = ?",
        (api_call["run_id"],),
    ).fetchone()
    assert run["status"] == "completed"
