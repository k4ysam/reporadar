"""Dashboard read-model queries.

These read across multiple JSONB sections of the v2 tables and project them
into UI-friendly dicts. They are the dashboard's only point of contact with
the database — the templates never see raw rows.
"""
from __future__ import annotations

import os
from datetime import datetime

import psycopg
from psycopg.rows import dict_row


def get_recent_runs(conn: psycopg.Connection, limit: int = 8) -> list[dict]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT run_id, started_at, completed_at, status, error_message, run_type
            FROM pipeline_runs
            ORDER BY started_at DESC
            LIMIT %s
            """,
            (limit,),
        )
        rows = cur.fetchall()
    return [
        {
            "run_id_short": row["run_id"][:12],
            "status": row["status"],
            "run_type": row["run_type"],
            "started_at": _fmt_dt(row["started_at"]),
            "duration": _duration(row["started_at"], row["completed_at"]),
            "error_message": row["error_message"],
        }
        for row in rows
    ]


def get_todays_scans(conn: psycopg.Connection) -> list[dict]:
    """GitHub candidates scanned today (any run)."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT DISTINCT ON (canonical_repo_key)
                canonical_repo_key,
                github,
                discovery,
                evaluation,
                created_at,
                updated_at
            FROM candidate_repository_evaluations
            WHERE source_type = 'github_discovery'
              AND created_at::date = CURRENT_DATE
            ORDER BY canonical_repo_key, created_at DESC
            """
        )
        rows = cur.fetchall()
    out = []
    for row in rows:
        gh = row.get("github") or {}
        discovery = row.get("discovery") or {}
        evaluation = row.get("evaluation") or {}
        out.append(
            {
                "full_name": gh.get("full_name", row["canonical_repo_key"]),
                "stars": gh.get("stars_count", 0),
                "first_seen_at": _fmt_dt(row["created_at"]),
                "last_scan_at": _fmt_dt(row["updated_at"]),
                "growth_pct": discovery.get("growth_percent"),
                "overall_score": (evaluation.get("scores") or {}).get("overall"),
                "github_url": gh.get("url") or f"https://github.com/{gh.get('full_name', '')}",
            }
        )
    out.sort(key=lambda x: (x["overall_score"] or 0, x["stars"]), reverse=True)
    return out


def get_recent_hackathons(conn: psycopg.Connection, limit: int = 25) -> list[dict]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT DISTINCT ON (canonical_repo_key)
                canonical_repo_key,
                hackathon,
                deduplication,
                updated_at
            FROM candidate_repository_evaluations
            WHERE source_type = 'devpost_discovery'
            ORDER BY canonical_repo_key, updated_at DESC
            LIMIT %s
            """,
            (limit,),
        )
        rows = cur.fetchall()
    return [
        {
            "project_name": (r.get("hackathon") or {}).get("project_name", "(unknown)"),
            "hackathon_name": (r.get("hackathon") or {}).get("hackathon_name") or "—",
            "prize": (r.get("hackathon") or {}).get("prize") or "—",
            "github_url": (r.get("hackathon") or {}).get("github_url"),
            "devpost_url": (r.get("hackathon") or {}).get("devpost_url"),
            "already_posted": bool((r.get("deduplication") or {}).get("already_posted")),
            "last_scan_at": _fmt_dt(r["updated_at"]),
        }
        for r in rows
    ]


def get_recent_evaluations(conn: psycopg.Connection, limit: int = 25) -> list[dict]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                id, source_type, canonical_repo_key,
                github, hackathon, discovery, evaluation
            FROM candidate_repository_evaluations
            WHERE evaluation IS NOT NULL
            ORDER BY (evaluation ->> 'evaluated_at')::timestamptz DESC
            LIMIT %s
            """,
            (limit,),
        )
        rows = cur.fetchall()
    out = []
    for row in rows:
        evaluation = row["evaluation"] or {}
        scores = evaluation.get("scores") or {}
        if row["source_type"] == "devpost_discovery":
            h = row.get("hackathon") or {}
            name = h.get("project_name") or row["canonical_repo_key"]
            url = h.get("devpost_url")
            content_type = "hackathon"
        else:
            gh = row.get("github") or {}
            name = gh.get("full_name") or row["canonical_repo_key"]
            url = gh.get("url") or (f"https://github.com/{gh.get('full_name')}" if gh else None)
            content_type = "repo"
        discovery = row.get("discovery") or {}
        out.append(
            {
                "content_type": content_type,
                "name": name,
                "url": url,
                "summary": evaluation.get("summary"),
                "why_interesting": evaluation.get("why_interesting"),
                "audience": evaluation.get("audience"),
                "novelty_score": scores.get("novelty"),
                "explainability_score": scores.get("explainability"),
                "overall_score": scores.get("overall"),
                "skip": bool(evaluation.get("skip")),
                "growth_pct": discovery.get("growth_percent"),
                "llm_provider": evaluation.get("provider") or "—",
                "evaluated_at": _fmt_dt(evaluation.get("evaluated_at")),
            }
        )
    return out


def get_recent_posts(conn: psycopg.Connection, limit: int = 20) -> list[dict]:
    """Posted/exported items from `posted_repositories`, flattened by channel.

    Each returned dict represents one channel post and is enriched enough that
    the dashboard can render the image inline (via `/media/<filename>`), show
    the full caption, hashtags, source links, and any validation warnings.
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                id, canonical_repo_url, github, hackathon, project_description,
                post_instances, posting_state, updated_at
            FROM posted_repositories
            ORDER BY updated_at DESC
            LIMIT %s
            """,
            (limit,),
        )
        rows = cur.fetchall()
    out = []
    for row in rows:
        gh = row.get("github") or {}
        h = row.get("hackathon") or {}
        project_desc = row.get("project_description") or {}
        name = gh.get("full_name") or h.get("project_name") or "(unknown)"
        subject_url = (
            gh.get("url")
            or (f"https://github.com/{gh.get('full_name')}" if gh.get("full_name") else None)
            or h.get("devpost_url")
        )
        for inst in row.get("post_instances") or []:
            media = inst.get("media") or []
            paths = [a.get("local_path") for a in media if a.get("local_path")]
            first_path = paths[0] if paths else None
            first_basename = os.path.basename(first_path) if first_path else None
            first_alt = (media[0].get("alt_text") if media else None) or None
            first_dims = None
            if media:
                w = media[0].get("width")
                hgt = media[0].get("height")
                if w and hgt:
                    first_dims = f"{w}×{hgt}"
            content = inst.get("content") or {}
            publication = inst.get("publication") or {}
            review = inst.get("review") or {}
            out.append(
                {
                    "id": inst.get("post_id"),
                    "channel": inst.get("platform"),
                    "status": inst.get("status"),
                    "name": name,
                    "subject_url": subject_url,
                    "summary": project_desc.get("ai_summary"),
                    "caption": content.get("text"),
                    "hook": content.get("hook"),
                    "hashtags": content.get("hashtags") or [],
                    "character_count": content.get("character_count") or 0,
                    "content_format": content.get("content_format"),
                    "source_links": inst.get("source_links") or [],
                    "card_paths": paths,
                    "first_path": first_path,
                    "first_path_basename": first_basename,
                    "first_alt_text": first_alt,
                    "first_image_dims": first_dims,
                    "slide_count": len(paths),
                    "external_post_url": publication.get("external_post_url"),
                    "review_notes": review.get("review_notes"),
                    "updated_at": _fmt_dt(row["updated_at"]),
                    "error_message": None,
                }
            )
    return out


def _fmt_dt(value) -> str:
    if value is None:
        return "—"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    try:
        dt = datetime.fromisoformat(str(value))
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(value)


def _duration(started, completed) -> str | None:
    if not started or not completed:
        return None
    try:
        if isinstance(started, str):
            started = datetime.fromisoformat(started)
        if isinstance(completed, str):
            completed = datetime.fromisoformat(completed)
        return f"{int((completed - started).total_seconds())}s"
    except Exception:
        return None
