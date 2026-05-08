from __future__ import annotations

import json
import sqlite3
from datetime import datetime


def get_todays_scans(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT
            r.id, r.full_name, r.star_count_at_last_scan,
            r.first_seen_at, r.last_scan_at,
            e.growth_pct, e.overall_score
        FROM repos_seen r
        LEFT JOIN (
            SELECT repo_id, growth_pct, overall_score
            FROM evaluations
            WHERE id IN (SELECT MAX(id) FROM evaluations WHERE repo_id IS NOT NULL GROUP BY repo_id)
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


def get_recent_hackathons(conn: sqlite3.Connection, limit: int = 25) -> list[dict]:
    rows = conn.execute(
        """
        SELECT id, devpost_url, project_name, hackathon_name, prize, github_url, last_scan_at, already_posted
        FROM hackathon_projects
        ORDER BY last_scan_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [
        {
            "project_name": row["project_name"],
            "hackathon_name": row["hackathon_name"] or "—",
            "prize": row["prize"] or "—",
            "github_url": row["github_url"],
            "devpost_url": row["devpost_url"],
            "already_posted": bool(row["already_posted"]),
            "last_scan_at": _fmt_dt(row["last_scan_at"]),
        }
        for row in rows
    ]


def get_recent_evaluations(conn: sqlite3.Connection, limit: int = 25) -> list[dict]:
    rows = conn.execute(
        """
        SELECT
            e.id, e.content_type, e.summary, e.why_interesting, e.audience,
            e.novelty_score, e.explainability_score, e.overall_score, e.skip,
            e.growth_pct, e.evaluated_at, e.llm_provider,
            r.full_name AS repo_name, h.project_name AS hack_name,
            r.full_name AS gh_repo_name, h.devpost_url AS hack_url, h.github_url AS hack_github
        FROM evaluations e
        LEFT JOIN repos_seen r          ON r.id = e.repo_id
        LEFT JOIN hackathon_projects h  ON h.id = e.hackathon_id
        ORDER BY e.evaluated_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    out = []
    for row in rows:
        if row["content_type"] == "repo":
            name = row["repo_name"] or "(unknown repo)"
            url = f"https://github.com/{row['repo_name']}" if row["repo_name"] else None
        else:
            name = row["hack_name"] or "(unknown project)"
            url = row["hack_url"]
        out.append(
            {
                "content_type": row["content_type"],
                "name": name,
                "url": url,
                "summary": row["summary"],
                "why_interesting": row["why_interesting"],
                "audience": row["audience"],
                "novelty_score": row["novelty_score"],
                "explainability_score": row["explainability_score"],
                "overall_score": row["overall_score"],
                "skip": bool(row["skip"]),
                "growth_pct": row["growth_pct"],
                "llm_provider": row["llm_provider"] or "—",
                "evaluated_at": _fmt_dt(row["evaluated_at"]),
            }
        )
    return out


def get_recent_posts(conn: sqlite3.Connection, limit: int = 20) -> list[dict]:
    rows = conn.execute(
        """
        SELECT
            p.id, p.content_type, p.media_type, p.status,
            p.error_message, p.card_paths, p.caption,
            r.full_name AS repo_name, h.project_name AS hack_name
        FROM posts p
        LEFT JOIN repos_seen r          ON r.id = p.repo_id
        LEFT JOIN hackathon_projects h  ON h.id = p.hackathon_id
        ORDER BY p.id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    out = []
    for row in rows:
        try:
            paths = json.loads(row["card_paths"]) if row["card_paths"] else []
        except Exception:
            paths = []
        out.append(
            {
                "id": row["id"],
                "content_type": row["content_type"],
                "media_type": row["media_type"],
                "status": row["status"],
                "name": row["repo_name"] or row["hack_name"] or "—",
                "error_message": row["error_message"],
                "card_paths": paths,
                "first_path": paths[0] if paths else None,
                "slide_count": len(paths),
                "caption": row["caption"],
            }
        )
    return out


def get_recent_runs(conn: sqlite3.Connection, limit: int = 8) -> list[dict]:
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
