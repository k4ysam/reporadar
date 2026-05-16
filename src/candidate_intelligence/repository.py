"""Data-access layer for `candidate_repository_evaluations`.

Every read or write of the candidate table goes through here, so that the
JSONB section ownership rules from v2 §13 are enforceable in one place.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from src.contracts.candidate import Candidate


def _candidate_to_row(candidate: Candidate) -> dict[str, Any]:
    source_payload = candidate.source.model_dump(mode="json")
    discovery_payload = candidate.discovery.model_dump(mode="json") if candidate.discovery else {}
    github_payload = candidate.github.model_dump(mode="json") if candidate.github else None
    hackathon_payload = candidate.hackathon.model_dump(mode="json") if candidate.hackathon else None
    enrichment_payload = candidate.enrichment.model_dump(mode="json") if candidate.enrichment else {}
    audit = {
        "created_by": "candidate_intelligence",
        "schema_version": 1,
    }
    return {
        "id": candidate.candidate_id,
        "run_id": candidate.run_id,
        "project_id": candidate.project_id,
        "canonical_repo_key": candidate.canonical_repo_key,
        "source_type": candidate.source.source_type,
        "status": "enriched" if candidate.enrichment else "discovered",
        "source": Jsonb(source_payload),
        "discovery": Jsonb(discovery_payload),
        "github": Jsonb(github_payload) if github_payload is not None else None,
        "hackathon": Jsonb(hackathon_payload) if hackathon_payload is not None else None,
        "enrichment": Jsonb(enrichment_payload),
        "deduplication": Jsonb(
            {
                "canonical_repo_key": candidate.canonical_repo_key,
                "already_posted": candidate.already_posted,
            }
        ),
        "audit": Jsonb(audit),
    }


def upsert_candidate(conn: psycopg.Connection, candidate: Candidate) -> None:
    """Insert or update a candidate row keyed by (run_id, canonical_repo_key).

    Only the sections owned by the discovery + enrichment stages are written;
    evaluation/ranking/selection/post_link are left as the DB defaults so the
    later services own those updates exclusively.
    """
    row = _candidate_to_row(candidate)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO candidate_repository_evaluations
                (id, run_id, project_id, canonical_repo_key, source_type, status,
                 source, discovery, github, hackathon, enrichment, deduplication, audit)
            VALUES
                (%(id)s, %(run_id)s, %(project_id)s, %(canonical_repo_key)s, %(source_type)s,
                 %(status)s, %(source)s, %(discovery)s, %(github)s, %(hackathon)s,
                 %(enrichment)s, %(deduplication)s, %(audit)s)
            ON CONFLICT (run_id, canonical_repo_key) DO UPDATE SET
                status = EXCLUDED.status,
                source = EXCLUDED.source,
                discovery = EXCLUDED.discovery,
                github = COALESCE(EXCLUDED.github, candidate_repository_evaluations.github),
                hackathon = COALESCE(EXCLUDED.hackathon, candidate_repository_evaluations.hackathon),
                enrichment = EXCLUDED.enrichment,
                deduplication = EXCLUDED.deduplication
            """,
            row,
        )
    conn.commit()


def set_evaluation(
    conn: psycopg.Connection,
    *,
    candidate_id: str,
    evaluation_payload: dict,
    skip: bool,
) -> None:
    new_status = "skipped" if skip else "evaluated"
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE candidate_repository_evaluations
            SET evaluation = %s,
                status = %s
            WHERE id = %s
            """,
            (Jsonb(evaluation_payload), new_status, candidate_id),
        )
    conn.commit()


def set_ranking(
    conn: psycopg.Connection,
    *,
    candidate_id: str,
    ranking_payload: dict,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE candidate_repository_evaluations
            SET ranking = %s,
                status = CASE WHEN status = 'evaluated' THEN 'ranked' ELSE status END
            WHERE id = %s
            """,
            (Jsonb(ranking_payload), candidate_id),
        )
    conn.commit()


def set_selection(
    conn: psycopg.Connection,
    *,
    candidate_id: str,
    selection_payload: dict,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE candidate_repository_evaluations
            SET selection = %s,
                status = CASE
                    WHEN (%s::jsonb ->> 'selected')::boolean THEN 'selected'
                    ELSE status
                END
            WHERE id = %s
            """,
            (Jsonb(selection_payload), Jsonb(selection_payload), candidate_id),
        )
    conn.commit()


def set_post_link(
    conn: psycopg.Connection,
    *,
    candidate_id: str,
    post_link_payload: dict,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE candidate_repository_evaluations
            SET post_link = %s,
                status = 'posted'
            WHERE id = %s
            """,
            (Jsonb(post_link_payload), candidate_id),
        )
    conn.commit()


def list_evaluated_for_run(conn: psycopg.Connection, run_id: str) -> list[dict]:
    """All evaluated, non-skipped, not-already-posted candidates in a run.

    Returned dicts contain the raw JSONB columns — the caller (Selection) is
    responsible for projecting them into RankingBreakdown / SelectionDecision.
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                id, run_id, project_id, canonical_repo_key, source_type,
                source, discovery, github, hackathon, enrichment,
                deduplication, evaluation
            FROM candidate_repository_evaluations
            WHERE run_id = %s
              AND evaluation IS NOT NULL
              AND COALESCE((evaluation ->> 'skip')::boolean, false) = false
              AND COALESCE((deduplication ->> 'already_posted')::boolean, false) = false
            ORDER BY (evaluation -> 'scores' ->> 'overall')::numeric DESC NULLS LAST
            """,
            (run_id,),
        )
        return list(cur.fetchall())


def already_posted_keys(conn: psycopg.Connection) -> set[str]:
    """All canonical_repo_keys for which we have a posted_repositories entry."""
    with conn.cursor() as cur:
        cur.execute("SELECT canonical_repo_key FROM posted_repositories")
        return {row[0] for row in cur.fetchall()}


def recent_evaluation_keys(
    conn: psycopg.Connection,
    *,
    within_days: int = 7,
) -> set[str]:
    """canonical_repo_keys that already received an evaluation within the
    dedup window. Used by the evaluation stage to skip rework."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=within_days)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT canonical_repo_key
            FROM candidate_repository_evaluations
            WHERE evaluation IS NOT NULL
              AND (evaluation ->> 'evaluated_at')::timestamptz > %s
            """,
            (cutoff,),
        )
        return {row[0] for row in cur.fetchall()}


def list_pending_for_run(
    conn: psycopg.Connection,
    run_id: str,
    *,
    limit: int,
) -> list[dict]:
    """Discovered/enriched candidates that have no evaluation yet."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                id, run_id, project_id, canonical_repo_key, source_type,
                source, discovery, github, hackathon, enrichment, deduplication
            FROM candidate_repository_evaluations
            WHERE run_id = %s
              AND evaluation IS NULL
              AND COALESCE((deduplication ->> 'already_posted')::boolean, false) = false
            ORDER BY created_at ASC
            LIMIT %s
            """,
            (run_id, limit),
        )
        return list(cur.fetchall())


def get_candidate(conn: psycopg.Connection, candidate_id: str) -> dict | None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT * FROM candidate_repository_evaluations WHERE id = %s
            """,
            (candidate_id,),
        )
        return cur.fetchone()
