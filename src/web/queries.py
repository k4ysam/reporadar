from __future__ import annotations

import sqlite3
from datetime import datetime, timezone


def get_todays_scans(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT
            r.id,
            r.full_name,
            r.star_count_at_last_scan,
            r.first_seen_at,
            r.last_scan_at,
            e.growth_pct,
            e.overall_score
        FROM repos_seen r
        LEFT JOIN (
            SELECT repo_id, growth_pct, overall_score
            FROM evaluations
            WHERE id IN (SELECT MAX(id) FROM evaluations GROUP BY repo_id)
        ) e ON e.repo_id = r.id
        WHERE date(r.last_scan_at) = date('now')
        ORDER BY COALESCE(e.overall_score, 0) DESC, r.star_count_at_last_scan DESC
        """
    ).fetchall()
    return [
        {
            "full_name": row["full_name"],
            "stars": row["star_count_at_last_scan"],
            "first_seen_at": _fmt_dt(row["first_seen_at"]),
            "last_scan_at": _fmt_dt(row["last_scan_at"]),
            "growth_pct": row["growth_pct"],
            "github_url": f"https://github.com/{row['full_name']}",
        }
        for row in rows
    ]


def get_evaluations_for_today(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT
            r.full_name,
            e.summary,
            e.why_interesting,
            e.audience,
            e.novelty_score,
            e.explainability_score,
            e.overall_score,
            e.growth_pct,
            e.approved,
            e.auto_expired,
            e.evaluated_at
        FROM evaluations e
        JOIN repos_seen r ON r.id = e.repo_id
        WHERE date(e.evaluated_at) = date('now')
        ORDER BY e.overall_score DESC
        """
    ).fetchall()
    return [
        {
            "full_name": row["full_name"],
            "github_url": f"https://github.com/{row['full_name']}",
            "summary": row["summary"],
            "why_interesting": row["why_interesting"],
            "audience": row["audience"],
            "novelty_score": row["novelty_score"],
            "explainability_score": row["explainability_score"],
            "overall_score": row["overall_score"],
            "growth_pct": row["growth_pct"],
            "status": _approval_status(row["approved"], row["auto_expired"]),
            "evaluated_at": _fmt_dt(row["evaluated_at"]),
        }
        for row in rows
    ]


def get_recent_runs(conn: sqlite3.Connection, limit: int = 5) -> list[dict]:
    rows = conn.execute(
        """
        SELECT run_id, started_at, completed_at, status, error_message
        FROM pipeline_runs
        ORDER BY started_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [
        {
            "run_id_short": row["run_id"][:8],
            "status": row["status"],
            "started_at": _fmt_dt(row["started_at"]),
            "duration": _duration(row["started_at"], row["completed_at"]),
            "error_message": row["error_message"],
        }
        for row in rows
    ]


def _fmt_dt(value: str | None) -> str:
    if not value:
        return "—"
    try:
        dt = datetime.fromisoformat(value)
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return value


def _duration(started: str | None, completed: str | None) -> str | None:
    if not started or not completed:
        return None
    try:
        s = datetime.fromisoformat(started)
        c = datetime.fromisoformat(completed)
        secs = int((c - s).total_seconds())
        return f"{secs}s"
    except Exception:
        return None


def _approval_status(approved, auto_expired) -> str:
    if auto_expired:
        return "auto-expired"
    if approved is None:
        return "pending"
    return "approved" if approved else "rejected"
