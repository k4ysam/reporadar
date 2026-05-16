"""Manual submission adapter.

Operators can paste a GitHub or Devpost URL into the dashboard; the URL is
normalized into a Candidate row that flows through the same pipeline as
scheduled discovery. Per v2 §16, manual submission is not a special one-off
path — it's another candidate source.
"""
from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlparse

import psycopg

from src.candidate_intelligence.repository import already_posted_keys, upsert_candidate
from src.candidate_intelligence.source_adapters.devpost_discovery.client import DevpostClient
from src.candidate_intelligence.source_adapters.devpost_discovery.scanner import _canonical_key
from src.candidate_intelligence.source_adapters.github_discovery.client import GithubClient
from src.candidate_intelligence.source_adapters.github_discovery.velocity import (
    github_snapshot_from_search,
)
from src.common.config import Settings
from src.common.ids import candidate_id, project_id_for
from src.contracts.candidate import Candidate, CandidateSource, HackathonSnapshot


def submit_manual(
    conn: psycopg.Connection,
    config: Settings,
    run_id: str,
    submitted_url: str,
    *,
    operator: str = "operator",
) -> Candidate:
    """Normalize a pasted URL into a Candidate and persist it.

    Supports github.com and devpost.com URLs. Raises ValueError for unsupported
    sources so the operator gets a clear error in the dashboard.
    """
    host = (urlparse(submitted_url).netloc or "").lower()
    if "github.com" in host:
        return _submit_github(conn, config, run_id, submitted_url, operator)
    if "devpost.com" in host:
        return _submit_devpost(conn, run_id, submitted_url, operator)
    raise ValueError(f"Unsupported submission host: {host or submitted_url!r}")


def _submit_github(
    conn: psycopg.Connection,
    config: Settings,
    run_id: str,
    url: str,
    operator: str,
) -> Candidate:
    path = urlparse(url).path.strip("/")
    parts = path.split("/")
    if len(parts) < 2:
        raise ValueError(f"GitHub URL must include owner/repo: {url!r}")
    full_name = f"{parts[0]}/{parts[1]}"
    canonical_key = f"github:{full_name}"

    client = GithubClient(conn, run_id, config.gh_token)
    repo = client.get_repo(full_name)
    github = github_snapshot_from_search(repo)

    source = CandidateSource(
        source_type="manual_submission",
        source_name="operator_paste",
        source_url=url,
        discovered_at=datetime.now(timezone.utc),
        discovery_reason="Manually submitted by operator.",
        manual_submission={"submitted_by": operator, "submitted_url": url},
    )

    candidate = Candidate(
        candidate_id=candidate_id(),
        project_id=project_id_for(canonical_key),
        canonical_repo_key=canonical_key,
        run_id=run_id,
        source=source,
        github=github,
        already_posted=canonical_key in already_posted_keys(conn),
    )
    upsert_candidate(conn, candidate)
    return candidate


def _submit_devpost(
    conn: psycopg.Connection,
    run_id: str,
    url: str,
    operator: str,
) -> Candidate:
    client = DevpostClient(conn, run_id)
    details = client.fetch_project(url)
    if not details:
        raise ValueError(f"Could not fetch Devpost project: {url!r}")

    canonical_key = _canonical_key(url)
    snapshot = HackathonSnapshot(
        devpost_url=url,
        project_name=details.get("project_name") or "Untitled",
        tagline=details.get("tagline"),
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
        source_type="manual_submission",
        source_name="operator_paste",
        source_url=url,
        discovered_at=datetime.now(timezone.utc),
        discovery_reason="Manually submitted by operator.",
        manual_submission={"submitted_by": operator, "submitted_url": url},
    )
    candidate = Candidate(
        candidate_id=candidate_id(),
        project_id=project_id_for(canonical_key),
        canonical_repo_key=canonical_key,
        run_id=run_id,
        source=source,
        hackathon=snapshot,
        already_posted=canonical_key in already_posted_keys(conn),
    )
    upsert_candidate(conn, candidate)
    return candidate
