from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from src.config import Settings
from src.models import Candidate


def _settings(**overrides):
    base = dict(gh_token="tok", gemini_api_key="AIza-test", max_evaluations_per_run=2)
    base.update(overrides)
    return Settings(**base)


def _candidate(repo_id: int, full_name: str):
    return Candidate(
        repo_id=repo_id,
        full_name=full_name,
        stars_now=500,
        stars_48h_ago=100,
        growth_pct=400.0,
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        first_seen_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
    )


def _seed_repo(db, full_name, repo_id):
    now = datetime.now(timezone.utc).isoformat()
    db.execute(
        "INSERT OR IGNORE INTO repos_seen (full_name, github_repo_id, first_seen_at, last_scan_at) "
        "VALUES (?, ?, ?, ?)",
        (full_name, repo_id, now, now),
    )
    db.commit()


GOOD_JSON = json.dumps({
    "summary": "Summary.", "why_interesting": "Because.", "audience": "Devs",
    "novelty_score": 8, "explainability_score": 9, "overall_score": 8.5, "skip": False,
})


def _mock_provider():
    p = MagicMock()
    p.name = "gemini"
    p.generate.return_value = GOOD_JSON
    return p


def _mock_github():
    client = MagicMock()
    client._request.return_value = MagicMock(ok=False, status_code=404, json=lambda: {})
    client.get_repo.return_value = {"description": None, "topics": [], "language": None}
    return client


def test_max_evaluations_cap(tmp_db, mock_run_id):
    for i in range(1, 6):
        _seed_repo(tmp_db, f"owner/repo-{i}", i)
    tmp_db.execute(
        "INSERT INTO pipeline_runs (run_id, started_at, status) VALUES (?, '2026-05-01', 'running')",
        (mock_run_id,),
    )
    tmp_db.commit()
    candidates = [_candidate(i, f"owner/repo-{i}") for i in range(1, 6)]
    from src.evaluator.batch import evaluate_candidates
    results = evaluate_candidates(
        candidates, _mock_provider(), _mock_github(), tmp_db, mock_run_id, _settings()
    )
    assert len(results) <= 2


def test_seven_day_dedup(tmp_db, mock_run_id):
    _seed_repo(tmp_db, "owner/repo-1", 1)
    repo_row = tmp_db.execute("SELECT id FROM repos_seen WHERE full_name='owner/repo-1'").fetchone()
    recent = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    tmp_db.execute(
        "INSERT INTO pipeline_runs (run_id, started_at, status) VALUES (?, '2026-05-01', 'running')",
        (mock_run_id,),
    )
    tmp_db.execute(
        "INSERT INTO evaluations (content_type, repo_id, run_id, evaluated_at, summary, why_interesting, audience, "
        "novelty_score, explainability_score, overall_score) VALUES ('repo', ?, ?, ?, 'x', 'y', 'z', 5, 5, 5)",
        (repo_row[0], mock_run_id, recent),
    )
    tmp_db.commit()
    candidates = [_candidate(1, "owner/repo-1")]
    from src.evaluator.batch import evaluate_candidates
    results = evaluate_candidates(
        candidates, _mock_provider(), _mock_github(), tmp_db, mock_run_id, _settings()
    )
    assert results == []


def test_exception_isolation(tmp_db, mock_run_id):
    for i in range(1, 3):
        _seed_repo(tmp_db, f"owner/repo-{i}", i)
    tmp_db.execute(
        "INSERT INTO pipeline_runs (run_id, started_at, status) VALUES (?, '2026-05-01', 'running')",
        (mock_run_id,),
    )
    tmp_db.commit()
    provider = MagicMock()
    provider.name = "gemini"
    provider.generate.side_effect = [Exception("boom"), GOOD_JSON]
    candidates = [_candidate(i, f"owner/repo-{i}") for i in range(1, 3)]
    from src.evaluator.batch import evaluate_candidates
    results = evaluate_candidates(
        candidates, provider, _mock_github(), tmp_db, mock_run_id, _settings()
    )
    assert len(results) == 1


def test_daily_budget_blocks(tmp_db, mock_run_id):
    """If today's api_calls already at limit, batch returns []."""
    _seed_repo(tmp_db, "owner/repo-1", 1)
    tmp_db.execute(
        "INSERT INTO pipeline_runs (run_id, started_at, status) VALUES (?, '2026-05-01', 'running')",
        (mock_run_id,),
    )
    tmp_db.commit()
    now = datetime.now(timezone.utc).isoformat()
    for _ in range(20):  # default daily limit
        tmp_db.execute(
            "INSERT INTO api_calls (run_id, service, endpoint, status_code, latency_ms, called_at) "
            "VALUES (?, 'gemini', '/x', 200, 10, ?)",
            (mock_run_id, now),
        )
    tmp_db.commit()
    candidates = [_candidate(1, "owner/repo-1")]
    from src.evaluator.batch import evaluate_candidates
    results = evaluate_candidates(
        candidates, _mock_provider(), _mock_github(), tmp_db, mock_run_id, _settings()
    )
    assert results == []
