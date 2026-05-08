from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from src.config import Settings
from src.models import Candidate


def _settings():
    return Settings(gh_token="tok", gemini_api_key="AIza-test")


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


def _mock_provider(response_text: str, name: str = "gemini"):
    p = MagicMock()
    p.name = name
    p.generate.return_value = response_text
    return p


def _mock_github():
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


def _seed_run(db, run_id):
    db.execute(
        "INSERT INTO pipeline_runs (run_id, started_at, status) VALUES (?, '2026-05-01', 'running')",
        (run_id,),
    )
    db.commit()


GOOD_JSON = json.dumps({
    "summary": "A blazing-fast KV store.",
    "why_interesting": "First pure-Python sub-1ms reads.",
    "audience": "Backend developers",
    "novelty_score": 8,
    "explainability_score": 9,
    "overall_score": 8.5,
    "skip": False,
})


class TestEvaluateCandidate:
    def test_returns_evaluation(self, tmp_db, mock_run_id):
        _seed_repo(tmp_db); _seed_run(tmp_db, mock_run_id)
        from src.evaluator.evaluator import evaluate_candidate
        result = evaluate_candidate(
            _candidate(), _mock_provider(GOOD_JSON), _mock_github(),
            tmp_db, mock_run_id, _settings(),
        )
        assert result.summary == "A blazing-fast KV store."
        assert result.overall_score == 8.5
        assert result.skip is False
        assert result.content_type == "repo"
        assert result.llm_provider == "gemini"

    def test_writes_db_row(self, tmp_db, mock_run_id):
        _seed_repo(tmp_db); _seed_run(tmp_db, mock_run_id)
        from src.evaluator.evaluator import evaluate_candidate
        evaluate_candidate(
            _candidate(), _mock_provider(GOOD_JSON), _mock_github(),
            tmp_db, mock_run_id, _settings(),
        )
        row = tmp_db.execute(
            "SELECT raw_response, llm_provider, content_type FROM evaluations"
        ).fetchone()
        assert row["raw_response"] == GOOD_JSON
        assert row["llm_provider"] == "gemini"
        assert row["content_type"] == "repo"

    def test_strips_json_code_fence(self, tmp_db, mock_run_id):
        _seed_repo(tmp_db); _seed_run(tmp_db, mock_run_id)
        fenced = f"```json\n{GOOD_JSON}\n```"
        from src.evaluator.evaluator import evaluate_candidate
        result = evaluate_candidate(
            _candidate(), _mock_provider(fenced), _mock_github(),
            tmp_db, mock_run_id, _settings(),
        )
        assert result.novelty_score == 8.0

    def test_retry_on_bad_json(self, tmp_db, mock_run_id):
        _seed_repo(tmp_db); _seed_run(tmp_db, mock_run_id)
        provider = MagicMock()
        provider.name = "claude"
        provider.generate.side_effect = ["not json at all", GOOD_JSON]
        from src.evaluator.evaluator import evaluate_candidate
        result = evaluate_candidate(
            _candidate(), provider, _mock_github(),
            tmp_db, mock_run_id, _settings(),
        )
        assert provider.generate.call_count == 2
        assert result.summary == "A blazing-fast KV store."

    def test_skip_flag_propagates(self, tmp_db, mock_run_id):
        _seed_repo(tmp_db); _seed_run(tmp_db, mock_run_id)
        skip_json = json.dumps({**json.loads(GOOD_JSON), "skip": True})
        from src.evaluator.evaluator import evaluate_candidate
        result = evaluate_candidate(
            _candidate(), _mock_provider(skip_json), _mock_github(),
            tmp_db, mock_run_id, _settings(),
        )
        assert result.skip is True


class TestEvaluateHackathon:
    def test_writes_hackathon_evaluation(self, tmp_db, mock_run_id):
        _seed_run(tmp_db, mock_run_id)
        now = datetime.now(timezone.utc).isoformat()
        tmp_db.execute(
            """INSERT INTO hackathon_projects
               (devpost_url, project_name, prize, github_url, first_seen_at, last_scan_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            ("https://devpost.com/software/x", "PixelChef", "Best Overall", "https://github.com/x/y", now, now),
        )
        tmp_db.commit()

        from src.evaluator.evaluator import evaluate_hackathon
        from src.models import HackathonCandidate

        candidate = HackathonCandidate(
            devpost_url="https://devpost.com/software/x",
            project_name="PixelChef",
            prize="Best Overall",
            github_url="https://github.com/x/y",
            first_seen_at=datetime.now(timezone.utc),
            technologies=["python", "ffmpeg"],
        )
        result = evaluate_hackathon(
            candidate, _mock_provider(GOOD_JSON, name="claude"),
            tmp_db, mock_run_id, _settings(),
        )
        assert result.content_type == "hackathon"
        assert result.full_name == "PixelChef"

        row = tmp_db.execute("SELECT content_type, hackathon_id FROM evaluations").fetchone()
        assert row["content_type"] == "hackathon"
        assert row["hackathon_id"] is not None
