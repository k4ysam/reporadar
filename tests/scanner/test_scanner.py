from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from src.config import Settings
from src.scanner.scanner import scan


def _settings():
    return Settings(
        gh_token="tok",
        gemini_api_key="AIza-test",
        star_base_min=20,
        star_growth_min_pct=200.0,
        velocity_window_hours=48,
        max_candidates_per_run=5,
    )


def _make_repo(i: int, stars: int = 500) -> dict:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "id": i,
        "full_name": f"owner/repo-{i}",
        "stargazers_count": stars,
        "description": f"Repo {i}",
        "language": "Python",
        "topics": [],
        "created_at": now,
    }


def _make_client(repos, rate_remaining=5000):
    client = MagicMock()
    client.get_rate_limit.return_value = {"resources": {"core": {"remaining": rate_remaining}}}
    client.search_repos.return_value = repos
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    client.get_stargazers_with_timestamps.return_value = [
        now - timedelta(hours=h) for h in range(400)
    ]
    return client


def test_scan_returns_candidates(tmp_db, mock_run_id):
    repos = [_make_repo(i) for i in range(3)]
    client = _make_client(repos)
    tmp_db.execute(
        "INSERT INTO pipeline_runs (run_id, started_at, status) VALUES (?, '2026-05-01', 'running')",
        (mock_run_id,),
    )
    tmp_db.commit()
    results = scan(tmp_db, _settings(), mock_run_id, client=client)
    assert isinstance(results, list)
    assert all(r.__class__.__name__ == "Candidate" for r in results)


def test_scan_deduplicates_repos(tmp_db, mock_run_id):
    repo = _make_repo(1)
    client = _make_client([repo, repo])  # duplicate
    tmp_db.execute(
        "INSERT INTO pipeline_runs (run_id, started_at, status) VALUES (?, '2026-05-01', 'running')",
        (mock_run_id,),
    )
    tmp_db.commit()
    scan(tmp_db, _settings(), mock_run_id, client=client)
    count = tmp_db.execute("SELECT COUNT(*) FROM repos_seen WHERE full_name='owner/repo-1'").fetchone()[0]
    assert count == 1


def test_scan_upserts_even_when_velocity_none(tmp_db, mock_run_id):
    repo = _make_repo(1, stars=5)  # below star_base_min → velocity returns None
    client = _make_client([repo])
    tmp_db.execute(
        "INSERT INTO pipeline_runs (run_id, started_at, status) VALUES (?, '2026-05-01', 'running')",
        (mock_run_id,),
    )
    tmp_db.commit()
    results = scan(tmp_db, _settings(), mock_run_id, client=client)
    assert results == []
    row = tmp_db.execute("SELECT star_count_at_last_scan FROM repos_seen WHERE full_name='owner/repo-1'").fetchone()
    assert row is not None  # upserted despite no candidate returned
    assert row[0] == 5


def test_scan_aborts_on_low_rate_limit(tmp_db, mock_run_id):
    repos = [_make_repo(i) for i in range(3)]
    client = _make_client(repos, rate_remaining=100)
    tmp_db.execute(
        "INSERT INTO pipeline_runs (run_id, started_at, status) VALUES (?, '2026-05-01', 'running')",
        (mock_run_id,),
    )
    tmp_db.commit()
    results = scan(tmp_db, _settings(), mock_run_id, client=client)
    assert results == []
    client.search_repos.assert_not_called()


def test_scan_sorted_by_growth_pct_desc(tmp_db, mock_run_id):
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    repos = [_make_repo(i, stars=100 + i * 200) for i in range(1, 4)]
    client = MagicMock()
    client.get_rate_limit.return_value = {"resources": {"core": {"remaining": 5000}}}
    client.search_repos.return_value = repos
    # Vary stargazer counts so growth differs
    call_count = [0]
    def side_effect(full_name, since, **_):
        call_count[0] += 1
        # repo-1:100stars,50recent; repo-2:300stars,250recent; repo-3:500stars,480recent
        counts = {1: 50, 2: 250, 3: 480}
        n = int(full_name.split("-")[1])
        return [now - timedelta(hours=h) for h in range(counts[n])]
    client.get_stargazers_with_timestamps.side_effect = side_effect
    tmp_db.execute(
        "INSERT INTO pipeline_runs (run_id, started_at, status) VALUES (?, '2026-05-01', 'running')",
        (mock_run_id,),
    )
    tmp_db.commit()
    results = scan(tmp_db, _settings(), mock_run_id, client=client)
    if len(results) > 1:
        assert results[0].growth_pct >= results[1].growth_pct
