from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.config import Settings
from src.models import Candidate


def _settings():
    return Settings(gh_token="tok", anthropic_api_key="sk", anthropic_model="claude-sonnet-4-6")


def _candidate():
    return Candidate(
        repo_id=1,
        full_name="owner/repo",
        stars_now=500,
        stars_48h_ago=100,
        growth_pct=400.0,
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        first_seen_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
    )


def _mock_response(text: str):
    msg = MagicMock()
    msg.content = [MagicMock(text=text)]
    return msg


def _mock_anthropic(response_text: str):
    client = MagicMock()
    client.messages.create.return_value = _mock_response(response_text)
    return client


def _mock_github():
    from src.evaluator.fetcher import RepoContext
    client = MagicMock()
    client._request.return_value = MagicMock(
        json=lambda: {"content": "", "message": "Not Found"},
        ok=False,
        status_code=404,
    )
    client.get_repo.return_value = {"description": "A tool", "topics": [], "language": "Python"}
    return client


def _seed_repo(db, full_name="owner/repo"):
    now = datetime.now(timezone.utc).isoformat()
    db.execute(
        "INSERT OR IGNORE INTO repos_seen (full_name, first_seen_at, last_scan_at) VALUES (?, ?, ?)",
        (full_name, now, now),
    )
    db.commit()


GOOD_JSON = json.dumps({
    "summary": "A blazing-fast KV store.",
    "why_interesting": "First pure-Python sub-1ms reads.",
    "audience": "Backend developers",
    "novelty_score": 8,
    "explainability_score": 9,
    "overall_score": 8.5,
})


class TestEvaluateCandidate:
    def test_returns_evaluation(self, tmp_db, mock_run_id):
        _seed_repo(tmp_db)
        tmp_db.execute(
            "INSERT INTO pipeline_runs (run_id, started_at, status) VALUES (?, '2026-05-01', 'running')",
            (mock_run_id,),
        )
        tmp_db.commit()
        from src.evaluator.evaluator import evaluate_candidate
        result = evaluate_candidate(
            _candidate(), _mock_anthropic(GOOD_JSON), _mock_github(),
            tmp_db, mock_run_id, _settings(),
        )
        assert result.summary == "A blazing-fast KV store."
        assert result.overall_score == 8.5

    def test_writes_db_row(self, tmp_db, mock_run_id):
        _seed_repo(tmp_db)
        tmp_db.execute(
            "INSERT INTO pipeline_runs (run_id, started_at, status) VALUES (?, '2026-05-01', 'running')",
            (mock_run_id,),
        )
        tmp_db.commit()
        from src.evaluator.evaluator import evaluate_candidate
        evaluate_candidate(
            _candidate(), _mock_anthropic(GOOD_JSON), _mock_github(),
            tmp_db, mock_run_id, _settings(),
        )
        row = tmp_db.execute("SELECT approved, claude_raw_response FROM evaluations").fetchone()
        assert row["approved"] is None  # pending
        assert row["claude_raw_response"] == GOOD_JSON

    def test_strips_json_code_fence(self, tmp_db, mock_run_id):
        _seed_repo(tmp_db)
        tmp_db.execute(
            "INSERT INTO pipeline_runs (run_id, started_at, status) VALUES (?, '2026-05-01', 'running')",
            (mock_run_id,),
        )
        tmp_db.commit()
        fenced = f"```json\n{GOOD_JSON}\n```"
        from src.evaluator.evaluator import evaluate_candidate
        result = evaluate_candidate(
            _candidate(), _mock_anthropic(fenced), _mock_github(),
            tmp_db, mock_run_id, _settings(),
        )
        assert result.novelty_score == 8.0

    def test_integer_scores_coerced_to_float(self, tmp_db, mock_run_id):
        _seed_repo(tmp_db)
        tmp_db.execute(
            "INSERT INTO pipeline_runs (run_id, started_at, status) VALUES (?, '2026-05-01', 'running')",
            (mock_run_id,),
        )
        tmp_db.commit()
        integer_json = json.dumps({
            "summary": "X", "why_interesting": "Y", "audience": "Z",
            "novelty_score": 8, "explainability_score": 9, "overall_score": 8,
        })
        from src.evaluator.evaluator import evaluate_candidate
        result = evaluate_candidate(
            _candidate(), _mock_anthropic(integer_json), _mock_github(),
            tmp_db, mock_run_id, _settings(),
        )
        assert isinstance(result.overall_score, float)

    def test_retry_on_bad_json(self, tmp_db, mock_run_id):
        _seed_repo(tmp_db)
        tmp_db.execute(
            "INSERT INTO pipeline_runs (run_id, started_at, status) VALUES (?, '2026-05-01', 'running')",
            (mock_run_id,),
        )
        tmp_db.commit()
        anthropic_client = MagicMock()
        anthropic_client.messages.create.side_effect = [
            _mock_response("not json at all"),
            _mock_response(GOOD_JSON),
        ]
        from src.evaluator.evaluator import evaluate_candidate
        result = evaluate_candidate(
            _candidate(), anthropic_client, _mock_github(),
            tmp_db, mock_run_id, _settings(),
        )
        assert anthropic_client.messages.create.call_count == 2
        assert result.summary == "A blazing-fast KV store."
