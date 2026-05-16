from __future__ import annotations

import logging
from pathlib import Path

import psycopg

from src.candidate_intelligence.repository import set_post_link
from src.common.config import Settings
from src.contracts.candidate import Candidate
from src.contracts.evaluation import Evaluation
from src.contracts.package import PostPackage
from src.contracts.selection import SelectionDecision
from src.publishing.adapters.manual_export import export_to_disk
from src.publishing.repository import upsert_posted_repository

_log = logging.getLogger(__name__)


def publish_packages(
    conn: psycopg.Connection,
    settings: Settings,
    *,
    candidate: Candidate,
    evaluation: Evaluation,
    selection: SelectionDecision,
    packages: list[PostPackage],
) -> tuple[str, list[Path]]:
    """Default manual-export publishing flow.

    1. Write a posted_repositories row (snapshot of repo + evaluation + ranking +
       one post_instance per package).
    2. Write a sidecar JSON per package in `output_dir` for the operator.
    3. Backfill the candidate row's `post_link` so the dashboard can join.

    Returns (posted_id, [json_paths]).
    """
    posted_id = upsert_posted_repository(
        conn,
        candidate=candidate,
        evaluation=evaluation,
        selection=selection,
        packages=packages,
    )

    json_paths: list[Path] = []
    for package in packages:
        json_path = export_to_disk(package, settings.output_dir)
        json_paths.append(json_path)
        _log.info("Exported %s package to %s", package.channel, json_path)

    set_post_link(
        conn,
        candidate_id=candidate.candidate_id,
        post_link_payload={
            "posted": False,
            "exported": True,
            "posted_project_id": posted_id,
            "post_ids": [pkg.post_id for pkg in packages],
            "exported_at": packages[0].created_at.isoformat() if packages else None,
        },
    )

    return posted_id, json_paths
