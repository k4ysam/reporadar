"""Candidate Intelligence service entry points.

The orchestrator calls these — they coordinate every internal stage:
    source_adapters → enrichment → evaluation → selection.
"""
from __future__ import annotations

import logging

import psycopg

from src.ai_gateway.llm.base import LLMProvider
from src.candidate_intelligence.evaluation.batch import (
    evaluate_hackathon_candidates,
    evaluate_repo_candidates,
)
from src.candidate_intelligence.selection.selector import select_top_candidate
from src.candidate_intelligence.source_adapters.devpost_discovery.scanner import scan_devpost
from src.candidate_intelligence.source_adapters.github_discovery.client import GithubClient
from src.candidate_intelligence.source_adapters.github_discovery.scanner import scan_github
from src.common.config import Settings
from src.contracts.candidate import Candidate
from src.contracts.evaluation import Evaluation
from src.contracts.selection import SelectionDecision

_log = logging.getLogger(__name__)


def discover_and_evaluate(
    conn: psycopg.Connection,
    config: Settings,
    run_id: str,
    provider: LLMProvider,
) -> tuple[list[Candidate], list[Evaluation]]:
    """Run all discovery sources + evaluation for one pipeline run.

    Returns (candidates, evaluations) for the orchestrator to hand to selection.
    """
    repo_candidates = scan_github(conn, config, run_id)
    hackathon_candidates = scan_devpost(conn, config, run_id)
    _log.info(
        "Discovered %d repo + %d hackathon candidates",
        len(repo_candidates),
        len(hackathon_candidates),
    )

    github_client = GithubClient(conn, run_id, config.gh_token)
    repo_evals = evaluate_repo_candidates(repo_candidates, provider, github_client, conn, config)
    hack_evals = evaluate_hackathon_candidates(hackathon_candidates, provider, conn, config)

    return repo_candidates + hackathon_candidates, repo_evals + hack_evals


def discover_evaluate_and_select(
    conn: psycopg.Connection,
    config: Settings,
    run_id: str,
    provider: LLMProvider,
    *,
    channels: list[str] | None = None,
) -> SelectionDecision | None:
    """Full Candidate Intelligence pipeline for one run.

    Stages:
        1. source_adapters: discover candidates
        2. enrichment + evaluation: score them
        3. selection: rank and pick the winner

    Returns the winning SelectionDecision, or None if no candidate is eligible.
    The orchestrator hands the result to Content Generation next.
    """
    _, evaluations = discover_and_evaluate(conn, config, run_id, provider)
    if not evaluations:
        return None
    return select_top_candidate(conn, run_id, channels=channels)


def evaluate_pending_candidates(
    conn: psycopg.Connection,
    config: Settings,
    run_id: str,
    provider: LLMProvider,
) -> list[Evaluation]:
    """Evaluate candidates already discovered for this run but not yet scored.

    Used by the CLI `evaluate` command — discovery happens elsewhere; this just
    catches up on un-evaluated rows.
    """
    from src.candidate_intelligence.repository import list_pending_for_run
    from src.contracts.candidate import (
        CandidateSource,
        DiscoverySignals,
        GithubSnapshot,
        HackathonSnapshot,
    )

    rows = list_pending_for_run(conn, run_id, limit=config.max_evaluations_per_run * 3)
    if not rows:
        return []

    github_client = GithubClient(conn, run_id, config.gh_token)
    repos: list[Candidate] = []
    hackathons: list[Candidate] = []
    for row in rows:
        source = CandidateSource(**row["source"])
        discovery = DiscoverySignals(**row["discovery"]) if row.get("discovery") else None
        github = GithubSnapshot(**row["github"]) if row.get("github") else None
        hackathon = HackathonSnapshot(**row["hackathon"]) if row.get("hackathon") else None
        candidate = Candidate(
            candidate_id=row["id"],
            project_id=row["project_id"],
            canonical_repo_key=row["canonical_repo_key"],
            run_id=row["run_id"],
            source=source,
            discovery=discovery,
            github=github,
            hackathon=hackathon,
        )
        (repos if github else hackathons).append(candidate)

    repo_evals = evaluate_repo_candidates(repos, provider, github_client, conn, config)
    hack_evals = evaluate_hackathon_candidates(hackathons, provider, conn, config)
    return repo_evals + hack_evals
