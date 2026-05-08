from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from src.config import Settings
from src.sources.github_repos.velocity import compute_velocity


NOW = datetime.now(timezone.utc)


def _settings(**overrides):
    base = dict(
        gh_token="tok",
        openai_api_key="sk-test",
        star_base_min=20,
        star_growth_min_pct=200.0,
        velocity_window_hours=48,
    )
    base.update(overrides)
    return Settings(**base)


def _repo(full_name="owner/repo", stars=500, repo_id=1, created_at=None):
    return {
        "id": repo_id,
        "full_name": full_name,
        "stargazers_count": stars,
        "description": "Test",
        "language": "Python",
        "topics": [],
        "created_at": (created_at or NOW).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def _fake_client(timestamps=None):
    client = MagicMock()
    client.get_stargazers_with_timestamps.return_value = timestamps or [
        NOW - timedelta(hours=1),
        NOW - timedelta(hours=2),
    ] * 200  # 400 recent stars
    return client


class TestComputeVelocityNewRepo:
    def test_passes_thresholds_returns_candidate(self, tmp_db):
        repo = _repo(stars=500)
        client = _fake_client([NOW - timedelta(hours=h) for h in range(400)])  # 400 recent
        result = compute_velocity(repo, tmp_db, client, _settings())
        # stars_window_ago = 500 - 400 = 100; delta=400; growth=400%
        assert result is not None
        assert result.full_name == "owner/repo"
        assert result.growth_pct > 200

    def test_below_growth_threshold_returns_none(self, tmp_db):
        repo = _repo(stars=100)
        # only 10 recent stars → growth = 10/90 * 100 ≈ 11%
        client = _fake_client([NOW - timedelta(hours=1)] * 10)
        result = compute_velocity(repo, tmp_db, client, _settings())
        assert result is None

    def test_below_star_base_returns_none(self, tmp_db):
        repo = _repo(stars=5)
        client = _fake_client([NOW - timedelta(hours=1)] * 4)
        result = compute_velocity(repo, tmp_db, client, _settings())
        assert result is None

    def test_zero_window_stars_no_div_by_zero(self, tmp_db):
        # All stars in window → stars_window_ago = 0; base = max(0,1) = 1
        repo = _repo(stars=30)
        client = _fake_client([NOW - timedelta(hours=h) for h in range(30)])
        result = compute_velocity(repo, tmp_db, client, _settings(star_growth_min_pct=100))
        # growth = 30/1 * 100 = 3000% — should pass
        assert result is not None


class TestComputeVelocityExistingRepo:
    def _insert_repo(self, db, full_name, last_star_count, already_posted=0, excluded_until=None):
        now = NOW.isoformat()
        db.execute(
            """INSERT INTO repos_seen (full_name, first_seen_at, last_scan_at, star_count_at_last_scan, already_posted, excluded_until)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (full_name, now, now, last_star_count, already_posted, excluded_until),
        )
        db.commit()

    def test_delta_based_calculation(self, tmp_db):
        self._insert_repo(tmp_db, "owner/repo", last_star_count=100)
        repo = _repo(stars=500)
        client = MagicMock()  # should NOT call stargazers for existing repo
        result = compute_velocity(repo, tmp_db, client, _settings())
        client.get_stargazers_with_timestamps.assert_not_called()
        assert result is not None
        assert result.stars_48h_ago == 100

    def test_already_posted_returns_none(self, tmp_db):
        self._insert_repo(tmp_db, "owner/repo", last_star_count=100, already_posted=1)
        result = compute_velocity(_repo(stars=500), tmp_db, MagicMock(), _settings())
        assert result is None

    def test_excluded_until_future_returns_none(self, tmp_db):
        future = (NOW + timedelta(days=30)).date().isoformat()
        self._insert_repo(tmp_db, "owner/repo", last_star_count=100, excluded_until=future)
        result = compute_velocity(_repo(stars=500), tmp_db, MagicMock(), _settings())
        assert result is None

    def test_excluded_until_past_allows_through(self, tmp_db):
        past = (NOW - timedelta(days=1)).date().isoformat()
        self._insert_repo(tmp_db, "owner/repo", last_star_count=100, excluded_until=past)
        result = compute_velocity(_repo(stars=500), tmp_db, MagicMock(), _settings())
        assert result is not None
