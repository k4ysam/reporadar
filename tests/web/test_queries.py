from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.web.queries import (
    get_recent_evaluations,
    get_recent_hackathons,
    get_recent_posts,
    get_recent_runs,
    get_todays_scans,
)


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
        "INSERT INTO repos_seen (full_name, first_seen_at, last_scan_at, star_count_at_last_scan) "
        "VALUES (?, ?, ?, ?)",
        (full_name, t.isoformat(), t.isoformat(), stars),
    )
    db.commit()
    return db.execute("SELECT id FROM repos_seen WHERE full_name=?", (full_name,)).fetchone()[0]


def _insert_repo_eval(db, repo_id, run_id, overall=7.5, growth_pct=300.0, days_ago=0):
    t = _now() - timedelta(days=days_ago)
    db.execute(
        """INSERT INTO evaluations
           (content_type, repo_id, run_id, evaluated_at, summary, why_interesting, audience,
            novelty_score, explainability_score, overall_score, growth_pct, llm_provider)
           VALUES ('repo', ?, ?, ?, 'sum', 'why', 'devs', 7, 8, ?, ?, 'gemini')""",
        (repo_id, run_id, t.isoformat(), overall, growth_pct),
    )
    db.commit()


def _insert_hackathon(db, project_name, prize="Best Overall"):
    now = _now().isoformat()
    db.execute(
        """INSERT INTO hackathon_projects
           (devpost_url, project_name, prize, github_url, first_seen_at, last_scan_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (f"https://devpost.com/software/{project_name}", project_name, prize,
         f"https://github.com/x/{project_name}", now, now),
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
        _insert_repo_eval(tmp_db, repo_id, run_id, growth_pct=350.0)
        result = get_todays_scans(tmp_db)
        assert result[0]["growth_pct"] == 350.0


class TestGetRecentEvaluations:
    def test_returns_repo_eval(self, tmp_db):
        run_id = _insert_run(tmp_db, "run-1")
        repo_id = _insert_repo(tmp_db, "owner/repo")
        _insert_repo_eval(tmp_db, repo_id, run_id)
        result = get_recent_evaluations(tmp_db)
        assert len(result) == 1
        assert result[0]["content_type"] == "repo"
        assert result[0]["name"] == "owner/repo"
        assert result[0]["url"] == "https://github.com/owner/repo"

    def test_returns_hackathon_eval(self, tmp_db):
        run_id = _insert_run(tmp_db, "run-1")
        _insert_hackathon(tmp_db, "PixelChef")
        hack_id = tmp_db.execute("SELECT id FROM hackathon_projects").fetchone()[0]
        tmp_db.execute(
            """INSERT INTO evaluations
               (content_type, hackathon_id, run_id, evaluated_at, summary, why_interesting, audience,
                novelty_score, explainability_score, overall_score, llm_provider)
               VALUES ('hackathon', ?, ?, ?, 's', 'w', 'a', 7, 8, 8.0, 'claude')""",
            (hack_id, run_id, _now().isoformat()),
        )
        tmp_db.commit()
        result = get_recent_evaluations(tmp_db)
        assert any(e["content_type"] == "hackathon" and e["name"] == "PixelChef" for e in result)

    def test_empty_db_returns_empty(self, tmp_db):
        assert get_recent_evaluations(tmp_db) == []


class TestGetRecentHackathons:
    def test_returns_inserted(self, tmp_db):
        _insert_hackathon(tmp_db, "Project-A")
        result = get_recent_hackathons(tmp_db)
        assert len(result) == 1
        assert result[0]["project_name"] == "Project-A"


class TestGetRecentPosts:
    def test_empty(self, tmp_db):
        assert get_recent_posts(tmp_db) == []


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

    def test_duration_computed(self, tmp_db):
        _insert_run(tmp_db, "run-1")
        result = get_recent_runs(tmp_db)
        assert result[0]["duration"] == "47s"
