"""Daily pipeline runner.

Per v2 §2.3: the orchestrator contains workflow logic only — no prompt
templates, scoring, scrape code, or formatting. After the service merges,
the orchestrator now coordinates four services:

    Candidate Intelligence  →  Content Generation  →  Publishing
    (discover + evaluate + select)  (text + media + package)  (export)
"""
from __future__ import annotations

import logging

import psycopg

from src.ai_gateway.factory import get_llm_provider
from src.candidate_intelligence import discover_evaluate_and_select
from src.candidate_intelligence.repository import get_candidate
from src.common.config import Settings
from src.content_generation import generate_post_package
from src.contracts.candidate import (
    Candidate,
    CandidateSource,
    DiscoverySignals,
    GithubSnapshot,
    HackathonSnapshot,
    RepoEnrichment,
)
from src.contracts.evaluation import Evaluation
from src.contracts.package import PostPackage
from src.orchestrator.runs import finish_run, start_run
from src.publishing import publish_packages

_log = logging.getLogger(__name__)


def run_pipeline(
    conn: psycopg.Connection,
    settings: Settings,
    *,
    channels: list[str] | None = None,
    requested_by: str = "manual",
) -> dict | None:
    """End-to-end workflow. Returns a summary dict, or None when nothing posted."""
    run_id = start_run(conn, requested_by=requested_by, config={"channels": channels or []})
    try:
        provider = get_llm_provider(settings, conn, run_id)

        # ── Stage 1 ──────────────────────────────────────────────────────
        # Candidate Intelligence: discover → enrich → evaluate → select.
        selection = discover_evaluate_and_select(
            conn, settings, run_id, provider, channels=channels
        )
        if selection is None:
            _log.info("No candidate selected for run %s.", run_id)
            finish_run(conn, run_id)
            return None

        candidate = _candidate_from_db(conn, selection.candidate_id, run_id)
        evaluation = _evaluation_from_db(conn, selection.candidate_id)
        if candidate is None or evaluation is None:
            raise RuntimeError(
                f"Failed to rehydrate candidate/evaluation for {selection.candidate_id}"
            )

        # ── Stage 2 ──────────────────────────────────────────────────────
        # Content Generation: text → media → packaging, per channel.
        target_channels = selection.selected_for_channels or ["instagram", "linkedin"]
        packages: list[PostPackage] = []
        for channel in target_channels:
            try:
                package = generate_post_package(
                    conn, settings, run_id, candidate, evaluation, provider, channel=channel
                )
                packages.append(package)
            except Exception as exc:
                _log.exception("Channel %s failed: %s", channel, exc)

        if not packages:
            finish_run(conn, run_id, error="All channels failed")
            return None

        # ── Stage 3 ──────────────────────────────────────────────────────
        # Publishing: write posted_repositories row + export sidecar JSONs.
        posted_id, json_paths = publish_packages(
            conn,
            settings,
            candidate=candidate,
            evaluation=evaluation,
            selection=selection,
            packages=packages,
        )

        finish_run(conn, run_id)
        return {
            "run_id": run_id,
            "posted_id": posted_id,
            "candidate_id": candidate.candidate_id,
            "project_id": candidate.project_id,
            "selection_score": selection.ranking_score,
            "channels": [pkg.channel for pkg in packages],
            "image_paths": [a.local_path for pkg in packages for a in pkg.media],
            "export_paths": [str(p) for p in json_paths],
        }
    except Exception as exc:
        finish_run(conn, run_id, error=str(exc))
        raise


def _candidate_from_db(
    conn: psycopg.Connection, candidate_id: str, run_id: str
) -> Candidate | None:
    row = get_candidate(conn, candidate_id)
    if row is None:
        return None
    return Candidate(
        candidate_id=row["id"],
        project_id=row["project_id"],
        canonical_repo_key=row["canonical_repo_key"],
        run_id=row["run_id"],
        source=CandidateSource(**row["source"]),
        discovery=DiscoverySignals(**row["discovery"]) if row.get("discovery") else None,
        github=GithubSnapshot(**row["github"]) if row.get("github") else None,
        hackathon=HackathonSnapshot(**row["hackathon"]) if row.get("hackathon") else None,
        enrichment=RepoEnrichment(**row["enrichment"]) if row.get("enrichment") else None,
        already_posted=(row.get("deduplication") or {}).get("already_posted", False),
    )


def _evaluation_from_db(conn: psycopg.Connection, candidate_id: str) -> Evaluation | None:
    row = get_candidate(conn, candidate_id)
    if row is None or not row.get("evaluation"):
        return None
    return Evaluation(**row["evaluation"])
