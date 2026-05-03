from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.web.queries import get_evaluations_for_today, get_recent_runs, get_todays_scans


def _now():
    return datetime.now(timezone.utc)


def _insert_run(db, run_id, status="completed", started_delta_hours=0):
    t = _now() - timedelta(hours=started_delta_hours)
    completed = (t + timedelta(seconds=47)).isoformat()
    db.execute(
        "INSERT INTO pipeline_runs (run_id, started_at, completed_at, status) VALUES (?, ?, ?, ?)",
        (run_id, t.isoformat(), completed, status),
    )
    db.commit()
    return run_id


def _insert_repo(db, full_name, stars=500, days_ago=0):
    t = _now() - timedelta(days=days_ago)
    db.execute(
        """INSERT INTO repos_seen (full_name, first_seen_at, last_scan_at, star_count_at_last_scan)
           VALUES (?, ?, ?, ?)""",
        (full_name, t.isoformat(), t.isoformat(), stars),
    )
    db.commit()
    return db.execute("SELECT id FROM repos_seen WHERE full_name=?", (full_name,)).fetchone()[0]


def _insert_evaluation(db, repo_id, run_id, overall_score=7.5, growth_pct=300.0, days_ago=0):
    t = _now() - timedelta(days=days_ago)
    db.execute(
        """INSERT INTO evaluations
           (repo_id, run_id, evaluated_at, summary, why_interesting, audience,
            novelty_score, explainability_score, overall_score, growth_pct)
           VALUES (?, ?, ?, 'sum', 'why', 'devs', 7, 8, ?, ?)""",
        (repo_id, run_id, t.isoformat(), overall_score, growth_pct),
    )
    db.commit()


class TestGetTodaysScans:
    def test_returns_todays_repos(self, tmp_db):
        _insert_repo(tmp_db, "owner/today-1", days_ago=0)
        _insert_repo(tmp_db, "owner/today-2", days_ago=0)
        _insert_repo(tmp_db, "owner/yesterday", days_ago=1)
        result = get_todays_scans(tmp_db)
        names = [r["full_name"] for r in result]
        assert "owner/today-1" in names
        assert "owner/today-2" in names
        assert "owner/yesterday" not in names

    def test_empty_db_returns_empty(self, tmp_db):
        assert get_todays_scans(tmp_db) == []

    def test_github_url_formed_correctly(self, tmp_db):
        _insert_repo(tmp_db, "owner/myrepo")
        result = get_todays_scans(tmp_db)
        assert result[0]["github_url"] == "https://github.com/owner/myrepo"

    def test_growth_pct_from_evaluation(self, tmp_db):
        run_id = _insert_run(tmp_db, "run-1")
        repo_id = _insert_repo(tmp_db, "owner/repo")
        _insert_evaluation(tmp_db, repo_id, run_id, growth_pct=350.0)
        result = get_todays_scans(tmp_db)
        assert result[0]["growth_pct"] == 350.0

    def test_growth_pct_none_when_no_evaluation(self, tmp_db):
        _insert_repo(tmp_db, "owner/repo")
        result = get_todays_scans(tmp_db)
        assert result[0]["growth_pct"] is None


class TestGetEvaluationsForToday:
    def test_returns_todays_evaluations(self, tmp_db):
        run_id = _insert_run(tmp_db, "run-1")
        repo_id = _insert_repo(tmp_db, "owner/repo")
        _insert_evaluation(tmp_db, repo_id, run_id, days_ago=0)
        result = get_evaluations_for_today(tmp_db)
        assert len(result) == 1
        assert result[0]["full_name"] == "owner/repo"

    def test_excludes_yesterday_evaluation(self, tmp_db):
        run_id = _insert_run(tmp_db, "run-1")
        repo_id = _insert_repo(tmp_db, "owner/repo")
        _insert_evaluation(tmp_db, repo_id, run_id, days_ago=1)
        assert get_evaluations_for_today(tmp_db) == []

    def test_empty_db_returns_empty(self, tmp_db):
        assert get_evaluations_for_today(tmp_db) == []

    def test_pending_status(self, tmp_db):
        run_id = _insert_run(tmp_db, "run-1")
        repo_id = _insert_repo(tmp_db, "owner/repo")
        _insert_evaluation(tmp_db, repo_id, run_id)
        result = get_evaluations_for_today(tmp_db)
        assert result[0]["status"] == "pending"

    def test_approved_status(self, tmp_db):
        run_id = _insert_run(tmp_db, "run-1")
        repo_id = _insert_repo(tmp_db, "owner/repo")
        _insert_evaluation(tmp_db, repo_id, run_id)
        tmp_db.execute("UPDATE evaluations SET approved=1")
        tmp_db.commit()
        result = get_evaluations_for_today(tmp_db)
        assert result[0]["status"] == "approved"


class TestGetRecentRuns:
    def test_returns_limit(self, tmp_db):
        for i in range(7):
            _insert_run(tmp_db, f"run-{i:02d}", started_delta_hours=i)
        result = get_recent_runs(tmp_db, limit=5)
        assert len(result) == 5

    def test_ordered_newest_first(self, tmp_db):
        _insert_run(tmp_db, "run-old", started_delta_hours=2)
        _insert_run(tmp_db, "run-new", started_delta_hours=0)
        result = get_recent_runs(tmp_db, limit=5)
        assert result[0]["run_id_short"] == "run-new"

    def test_empty_db_returns_empty(self, tmp_db):
        assert get_recent_runs(tmp_db) == []

    def test_duration_computed(self, tmp_db):
        _insert_run(tmp_db, "run-1")
        result = get_recent_runs(tmp_db)
        assert result[0]["duration"] == "47s"
