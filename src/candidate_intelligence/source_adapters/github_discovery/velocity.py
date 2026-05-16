from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import psycopg

from src.candidate_intelligence.source_adapters.github_discovery.client import GithubClient
from src.common.config import Settings
from src.contracts.candidate import DiscoverySignals, GithubSnapshot


def github_snapshot_from_search(repo: dict) -> GithubSnapshot:
    full_name = repo["full_name"]
    owner, _, name = full_name.partition("/")
    return GithubSnapshot(
        owner=owner,
        repo=name,
        full_name=full_name,
        url=repo.get("html_url") or f"https://github.com/{full_name}",
        description=repo.get("description"),
        homepage_url=repo.get("homepage"),
        primary_language=repo.get("language"),
        topics=list(repo.get("topics") or []),
        license=(repo.get("license") or {}).get("spdx_id"),
        stars_count=repo.get("stargazers_count", 0),
        forks_count=repo.get("forks_count", 0),
        open_issues_count=repo.get("open_issues_count", 0),
        watchers_count=repo.get("watchers_count", 0),
        default_branch=repo.get("default_branch"),
        created_at=_parse_dt(repo.get("created_at")),
        pushed_at=_parse_dt(repo.get("pushed_at")),
        archived=bool(repo.get("archived")),
        is_fork=bool(repo.get("fork")),
        github_repo_id=repo.get("id"),
    )


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def compute_velocity_signals(
    repo: dict,
    conn: psycopg.Connection,
    client: GithubClient,
    config: Settings,
) -> tuple[DiscoverySignals, bool]:
    """Return (signals, passes_threshold) for one GitHub search hit.

    Looks up the previous-scan star count from the most recent candidate row
    for this canonical repo (across any run) — that's the v2 equivalent of the
    legacy `repos_seen.star_count_at_last_scan`.
    """
    full_name = repo["full_name"]
    stars_now = repo.get("stargazers_count", 0)
    canonical_key = f"github:{full_name}"

    prev = _previous_star_count(conn, canonical_key)
    if prev is None:
        window_start = datetime.now(timezone.utc) - timedelta(hours=config.velocity_window_hours)
        recent = client.get_stargazers_with_timestamps(full_name, since=window_start)
        stars_window_ago = max(stars_now - len(recent), 0)
    else:
        stars_window_ago = prev

    delta = stars_now - stars_window_ago
    base = max(stars_window_ago, 1)
    growth_pct = round((delta / base) * 100, 2)

    signals = DiscoverySignals(
        stars_at_discovery=stars_now,
        stars_window_ago=stars_window_ago,
        star_delta=delta,
        growth_percent=growth_pct,
        window_hours=config.velocity_window_hours,
        pushed_recently=bool(repo.get("pushed_at")),
    )

    if stars_now < config.star_base_min:
        return signals, False
    if delta < config.star_base_min:
        return signals, False
    if growth_pct < config.star_growth_min_pct:
        return signals, False
    return signals, True


def _previous_star_count(conn: psycopg.Connection, canonical_key: str) -> int | None:
    """Most recent observed star count for this canonical_repo_key."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT (github ->> 'stars_count')::int
            FROM candidate_repository_evaluations
            WHERE canonical_repo_key = %s
              AND github IS NOT NULL
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (canonical_key,),
        )
        row = cur.fetchone()
        return int(row[0]) if row and row[0] is not None else None
