from __future__ import annotations

from unittest.mock import patch

import pytest
import responses as resp_mock

from src.sources.github_repos.client import GithubClient


@pytest.fixture
def client(tmp_db, mock_run_id):
    return GithubClient(tmp_db, mock_run_id, "ghp_test_token")


@resp_mock.activate
def test_get_rate_limit_success(client, tmp_db, mock_run_id):
    tmp_db.execute(
        "INSERT INTO pipeline_runs (run_id, started_at, status) VALUES (?, '2026-05-01', 'running')",
        (mock_run_id,),
    )
    tmp_db.commit()
    resp_mock.add(resp_mock.GET, "https://api.github.com/rate_limit", json={"resources": {"core": {"remaining": 4999}}})
    data = client.get_rate_limit()
    assert data["resources"]["core"]["remaining"] == 4999
    row = tmp_db.execute("SELECT * FROM api_calls WHERE run_id=?", (mock_run_id,)).fetchone()
    assert row["service"] == "github"
    assert row["status_code"] == 200
    assert row["latency_ms"] >= 0


@resp_mock.activate
def test_search_repos_returns_items(client, tmp_db, mock_run_id):
    tmp_db.execute(
        "INSERT INTO pipeline_runs (run_id, started_at, status) VALUES (?, '2026-05-01', 'running')",
        (mock_run_id,),
    )
    tmp_db.commit()
    resp_mock.add(
        resp_mock.GET,
        "https://api.github.com/search/repositories",
        json={"items": [{"id": 1, "full_name": "owner/repo"}]},
    )
    items = client.search_repos("stars:>100")
    assert len(items) == 1
    assert items[0]["full_name"] == "owner/repo"


@resp_mock.activate
def test_429_retries(client, tmp_db, mock_run_id):
    tmp_db.execute(
        "INSERT INTO pipeline_runs (run_id, started_at, status) VALUES (?, '2026-05-01', 'running')",
        (mock_run_id,),
    )
    tmp_db.commit()
    resp_mock.add(resp_mock.GET, "https://api.github.com/rate_limit", status=429, headers={"Retry-After": "0"})
    resp_mock.add(resp_mock.GET, "https://api.github.com/rate_limit", json={"resources": {}})
    with patch("time.sleep"):
        data = client.get_rate_limit()
    assert data == {"resources": {}}


@resp_mock.activate
def test_stargazers_stops_before_window(client, tmp_db, mock_run_id):
    from datetime import datetime, timedelta, timezone

    tmp_db.execute(
        "INSERT INTO pipeline_runs (run_id, started_at, status) VALUES (?, '2026-05-01', 'running')",
        (mock_run_id,),
    )
    tmp_db.commit()
    now = datetime.now(timezone.utc)
    recent = now - timedelta(hours=1)
    old = now - timedelta(hours=100)
    resp_mock.add(
        resp_mock.GET,
        "https://api.github.com/repos/owner/repo/stargazers",
        json=[
            {"starred_at": recent.strftime("%Y-%m-%dT%H:%M:%SZ"), "user": {}},
            {"starred_at": old.strftime("%Y-%m-%dT%H:%M:%SZ"), "user": {}},
        ],
    )
    since = now - timedelta(hours=48)
    timestamps = client.get_stargazers_with_timestamps("owner/repo", since=since, max_pages=2)
    assert len(timestamps) == 1  # old one excluded
