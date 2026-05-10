from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from src.config import Settings
from src.models import Candidate
from src.sources.github_repos.client import GithubClient


def compute_velocity(
    repo: dict,
    db: sqlite3.Connection,
    client: GithubClient,
    config: Settings,
) -> Candidate | None:
    full_name: str = repo["full_name"]
    stars_now: int = repo.get("stargazers_count", 0)
    github_repo_id: int = repo["id"]

    row = db.execute(
        """
        SELECT id, first_seen_at, star_count_at_last_scan, excluded_until, already_posted
        FROM repos_seen
        WHERE full_name = ? OR github_repo_id = ?
        ORDER BY CASE WHEN full_name = ? THEN 0 ELSE 1 END
        LIMIT 1
        """,
        (full_name, github_repo_id, full_name),
    ).fetchone()

    if row:
        if row["already_posted"]:
            return None
        if row["excluded_until"]:
            excl = datetime.fromisoformat(row["excluded_until"]).date()
            if excl >= datetime.now(timezone.utc).date():
                return None
        stars_window_ago = row["star_count_at_last_scan"]
    else:
        # New repo — fetch stargazer timestamps to estimate stars at window start
        window_start = datetime.now(timezone.utc) - timedelta(hours=config.velocity_window_hours)
        recent = client.get_stargazers_with_timestamps(full_name, since=window_start)
        stars_window_ago = max(stars_now - len(recent), 0)

    delta = stars_now - stars_window_ago
    base = max(stars_window_ago, 1)  # guard against div-by-zero on brand-new repos
    growth_pct = (delta / base) * 100

    if stars_now < config.star_base_min:
        return None
    if delta < config.star_base_min:
        return None
    if growth_pct < config.star_growth_min_pct:
        return None

    created_at = datetime.fromisoformat(repo["created_at"].replace("Z", "+00:00"))
    first_seen_at = datetime.now(timezone.utc) if not row else datetime.fromisoformat(row["first_seen_at"])

    return Candidate(
        repo_id=github_repo_id,
        full_name=full_name,
        description=repo.get("description"),
        stars_now=stars_now,
        stars_48h_ago=stars_window_ago,
        growth_pct=round(growth_pct, 2),
        language=repo.get("language"),
        topics=repo.get("topics", []),
        created_at=created_at,
        first_seen_at=first_seen_at,
    )
