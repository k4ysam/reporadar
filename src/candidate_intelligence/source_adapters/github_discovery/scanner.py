from __future__ import annotations

from datetime import datetime, timedelta, timezone

import psycopg

from src.candidate_intelligence.repository import already_posted_keys, upsert_candidate
from src.candidate_intelligence.source_adapters.github_discovery.client import GithubClient
from src.candidate_intelligence.source_adapters.github_discovery.velocity import (
    compute_velocity_signals,
    github_snapshot_from_search,
)
from src.common.config import Settings
from src.common.ids import candidate_id, project_id_for
from src.contracts.candidate import Candidate, CandidateSource


def scan_github(
    conn: psycopg.Connection,
    config: Settings,
    run_id: str,
    client: GithubClient | None = None,
) -> list[Candidate]:
    """Discover rising GitHub repos and upsert one candidate row per hit."""
    client = client or GithubClient(conn, run_id, config.gh_token)

    rate = client.get_rate_limit()
    remaining = rate.get("resources", {}).get("core", {}).get("remaining", 0)
    if remaining < 500:
        return []

    window_start = (
        datetime.now(timezone.utc) - timedelta(hours=config.velocity_window_hours)
    ).date().isoformat()
    max_age_cutoff = (
        datetime.now(timezone.utc) - timedelta(days=config.repo_max_age_days)
    ).date().isoformat()
    queries = [
        f"created:>{window_start} stars:>={config.star_base_min} sort:stars-desc",
        f"pushed:>{window_start} created:>{max_age_cutoff} stars:>={config.star_base_min} sort:updated",
    ]

    posted_keys = already_posted_keys(conn)

    seen_names: set[str] = set()
    hits: list[dict] = []
    for q in queries:
        for repo in client.search_repos(q, per_page=50):
            if repo["full_name"] not in seen_names:
                seen_names.add(repo["full_name"])
                hits.append(repo)

    candidates: list[Candidate] = []
    for repo in hits:
        canonical_key = f"github:{repo['full_name']}"
        signals, passes = compute_velocity_signals(repo, conn, client, config)
        github = github_snapshot_from_search(repo)

        source = CandidateSource(
            source_type="github_discovery",
            source_name="github_search_api",
            source_url=github.url,
            discovered_at=datetime.now(timezone.utc),
            discovery_reason="High star growth in velocity window."
            if passes
            else "Tracked for baseline; below threshold.",
        )

        candidate = Candidate(
            candidate_id=candidate_id(),
            project_id=project_id_for(canonical_key),
            canonical_repo_key=canonical_key,
            run_id=run_id,
            source=source,
            discovery=signals,
            github=github,
            already_posted=canonical_key in posted_keys,
        )

        upsert_candidate(conn, candidate)

        if passes and not candidate.already_posted:
            candidates.append(candidate)

    candidates.sort(key=lambda c: c.discovery.growth_percent if c.discovery else 0, reverse=True)
    return candidates[: config.max_candidates_per_run]
