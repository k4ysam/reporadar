from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import responses as resp_mock

from src.cli import cmd_linkedin_preview, cmd_verify_env
from src.config import Settings
from src.models import RenderResult


@resp_mock.activate
def test_verify_env_uses_persisted_run_id_for_api_logging(tmp_db):
    settings = Settings(gh_token="ghp_test", openai_api_key="sk-test")
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


def _seed_repo_evaluation(db) -> int:
    now = datetime.now(timezone.utc).isoformat()
    cursor = db.execute(
        """
        INSERT INTO repos_seen (
            full_name,
            github_repo_id,
            first_seen_at,
            last_scan_at,
            star_count_at_last_scan
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        ("awesome-co/zerodb", 123, now, now, 1420),
    )
    repo_id = cursor.lastrowid
    eval_cursor = db.execute(
        """
        INSERT INTO evaluations (
            content_type,
            repo_id,
            evaluated_at,
            summary,
            why_interesting,
            audience,
            novelty_score,
            explainability_score,
            overall_score,
            skip,
            growth_pct,
            llm_provider
        )
        VALUES ('repo', ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
        """,
        (
            repo_id,
            now,
            "A 1ms KV store in pure Python.",
            "It can replace a Redis sidecar for small apps.",
            "Backend developers",
            8.5,
            9.0,
            8.7,
            380.0,
            "openai",
        ),
    )
    db.commit()
    return int(eval_cursor.lastrowid)


def test_linkedin_preview_generates_manual_package(tmp_db, tmp_path, capsys):
    _seed_repo_evaluation(tmp_db)
    settings = Settings(gh_token="ghp_test", openai_api_key="sk-test", output_dir=str(tmp_path))
    args = SimpleNamespace(
        evaluation_id=None,
        include_skipped=False,
        language="Python",
        topics=["kv", "storage"],
    )
    provider = SimpleNamespace(
        name="openai",
        generate=lambda prompt, system=None: "zerodb is getting attention from backend developers.",
    )
    poster_path = tmp_path / "poster.jpg"

    with patch("src.llm.provider.get_provider", return_value=provider):
        with patch(
            "src.linkedin.package.render_linkedin_repo_poster",
            return_value=RenderResult(media_type="single", paths=[str(poster_path)]),
        ):
            result = cmd_linkedin_preview(args, settings, tmp_db)

    assert result == 0
    captured = capsys.readouterr()
    assert "LinkedIn commentary" in captured.out
    assert "zerodb is getting attention" in captured.out
    assert str(poster_path) in captured.out
    assert "https://github.com/awesome-co/zerodb" in captured.out

    package_paths = list(tmp_path.glob("linkedin_awesome-co-zerodb_*.json"))
    assert len(package_paths) == 1
    package = json.loads(package_paths[0].read_text(encoding="utf-8"))
    assert package["commentary"] == "zerodb is getting attention from backend developers."
    assert package["image_paths"] == [str(poster_path)]
    assert package["repo_url"] == "https://github.com/awesome-co/zerodb"
    assert package["source_name"] == "awesome-co/zerodb"

    run = tmp_db.execute(
        "SELECT status FROM pipeline_runs ORDER BY started_at DESC LIMIT 1"
    ).fetchone()
    assert run["status"] == "completed"
