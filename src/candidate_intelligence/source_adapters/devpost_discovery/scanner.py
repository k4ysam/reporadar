from __future__ import annotations

from datetime import datetime, timezone

import psycopg

from src.candidate_intelligence.repository import already_posted_keys, upsert_candidate
from src.candidate_intelligence.source_adapters.devpost_discovery.client import DevpostClient
from src.common.config import Settings
from src.common.ids import candidate_id, project_id_for
from src.contracts.candidate import Candidate, CandidateSource, HackathonSnapshot


def _canonical_key(devpost_url: str) -> str:
    slug = devpost_url.rstrip("/").split("/")[-1]
    return f"devpost:{slug}"


def scan_devpost(
    conn: psycopg.Connection,
    config: Settings,
    run_id: str,
    client: DevpostClient | None = None,
) -> list[Candidate]:
    """Scan Devpost for recent prize-winning projects with a GitHub link.

    PRD §1 filters: project must have GitHub link AND prize-winning status.
    Non-eligible projects are still written to the candidates table for tracking.
    """
    client = client or DevpostClient(conn, run_id)

    listings = client.list_recent_software(limit=config.devpost_max_projects_per_run)
    if not listings:
        return []

    posted_keys = already_posted_keys(conn)
    candidates: list[Candidate] = []

    for listing in listings:
        url = listing["devpost_url"]
        canonical_key = _canonical_key(url)

        details = client.fetch_project(url)
        if not details:
            continue

        eligible = bool(details.get("github_url")) and bool(details.get("prize"))

        snapshot = HackathonSnapshot(
            devpost_url=url,
            project_name=details.get("project_name") or listing.get("project_name") or "Untitled",
            tagline=details.get("tagline") or listing.get("tagline"),
            hackathon_name=details.get("hackathon_name"),
            prize=details.get("prize"),
            team=details.get("team"),
            github_url=details.get("github_url"),
            demo_url=details.get("demo_url"),
            submitted_at=details.get("submitted_at"),
            description=details.get("description"),
            technologies=details.get("technologies", []),
        )
        source = CandidateSource(
            source_type="devpost_discovery",
            source_name="devpost_scrape",
            source_url=url,
            discovered_at=datetime.now(timezone.utc),
            discovery_reason="Prize-winning Devpost project with GitHub link."
            if eligible
            else "Tracked for baseline; missing GitHub link or prize.",
        )

        candidate = Candidate(
            candidate_id=candidate_id(),
            project_id=project_id_for(canonical_key),
            canonical_repo_key=canonical_key,
            run_id=run_id,
            source=source,
            hackathon=snapshot,
            already_posted=canonical_key in posted_keys,
        )

        upsert_candidate(conn, candidate)

        if eligible and not candidate.already_posted:
            candidates.append(candidate)

    return candidates
