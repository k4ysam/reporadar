from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from src.config import Settings
from src.models import Candidate
from src.scanner.github_client import GithubClient
from src.scanner.velocity import compute_velocity


def scan(
    db: sqlite3.Connection,
    config: Settings,
    run_id: str,
    client: GithubClient | None = None,
) -> list[Candidate]:
    if client is None:
        client = GithubClient(db, run_id, config.gh_token)

    rate = client.get_rate_limit()
    remaining = rate.get("resources", {}).get("core", {}).get("remaining", 0)
    if remaining < 500:
        return []

    window_start = (datetime.now(timezone.utc) - timedelta(hours=config.velocity_window_hours)).date().isoformat()
    max_age_cutoff = (datetime.now(timezone.utc) - timedelta(days=config.repo_max_age_days)).date().isoformat()
    queries = [
        f"created:>{window_start} stars:>={config.star_base_min} sort:stars-desc",
        f"pushed:>{window_start} created:>{max_age_cutoff} stars:>={config.star_base_min} sort:updated",
    ]

    seen_names: set[str] = set()
    repos: list[dict] = []
    for q in queries:
        for repo in client.search_repos(q, per_page=50):
            if repo["full_name"] not in seen_names:
                seen_names.add(repo["full_name"])
                repos.append(repo)

    now_iso = datetime.now(timezone.utc).isoformat()
    candidates: list[Candidate] = []

    for repo in repos:
        candidate = compute_velocity(repo, db, client, config)

        # Always upsert star count so next run's delta is accurate
        db.execute(
            """
            INSERT INTO repos_seen (full_name, github_repo_id, first_seen_at, last_scan_at, star_count_at_last_scan)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(full_name) DO UPDATE SET
                last_scan_at = excluded.last_scan_at,
                star_count_at_last_scan = excluded.star_count_at_last_scan,
                github_repo_id = COALESCE(repos_seen.github_repo_id, excluded.github_repo_id)
            """,
            (repo["full_name"], repo["id"], now_iso, now_iso, repo.get("stargazers_count", 0)),
        )
        db.commit()

        if candidate is not None:
            candidates.append(candidate)

    candidates.sort(key=lambda c: c.growth_pct, reverse=True)
    return candidates[: config.max_candidates_per_run]
