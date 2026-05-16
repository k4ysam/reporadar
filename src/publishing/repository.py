"""Data-access for `posted_repositories`.

Owned exclusively by the Publishing service. Other services read via API /
read model, never write here directly.
"""
from __future__ import annotations

from datetime import datetime, timezone

import psycopg
from psycopg.types.json import Jsonb

from src.common.ids import posted_repo_id_for
from src.contracts.candidate import Candidate
from src.contracts.content import GeneratedContent
from src.contracts.evaluation import Evaluation
from src.contracts.media import MediaAsset
from src.contracts.package import PostPackage
from src.contracts.selection import SelectionDecision


def upsert_posted_repository(
    conn: psycopg.Connection,
    *,
    candidate: Candidate,
    evaluation: Evaluation,
    selection: SelectionDecision,
    packages: list[PostPackage],
) -> str:
    """Insert (or merge into existing) posted_repositories row + add post_instances.

    Returns the posted_repository row id.
    """
    posted_id = posted_repo_id_for(candidate.project_id)
    canonical_url = candidate.github.url if candidate.github else (
        candidate.hackathon.devpost_url if candidate.hackathon else ""
    )

    github_payload = candidate.github.model_dump(mode="json") if candidate.github else None
    hackathon_payload = candidate.hackathon.model_dump(mode="json") if candidate.hackathon else None

    project_description = {
        "ai_summary": evaluation.summary,
        "why_interesting": evaluation.why_interesting,
        "target_audience": [evaluation.audience],
        "tags": candidate.github.topics if candidate.github else [],
    }
    source_payload = {
        "original_source_type": candidate.source.source_type,
        "source_urls": [candidate.source.source_url],
        "discovery_run_id": candidate.run_id,
        "candidate_id": candidate.candidate_id,
        "evaluation_id": evaluation.evaluation_id,
        "selection_id": selection.selection_id,
    }
    evaluation_snapshot = evaluation.model_dump(mode="json")
    ranking_snapshot = {
        "ranking_version": selection.ranking_version,
        "ranking_score": selection.ranking_score,
        "rank_in_run": selection.rank_in_run,
        "total_candidates_in_run": selection.total_candidates_in_run,
        "ranked_at": (selection.selected_at or datetime.now(timezone.utc)).isoformat(),
        "selection_reason": "; ".join(selection.ranking_reasons),
    }
    post_instances_payload = [_post_instance_for(pkg) for pkg in packages]

    now = datetime.now(timezone.utc)
    posting_state = {
        "has_been_posted": False,
        "posted_platforms": [],
        "exported_platforms": [pkg.channel for pkg in packages],
        "first_posted_at": None,
        "last_posted_at": None,
        "do_not_repost": True,
    }
    audit = {
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "created_by": "publishing_service",
        "schema_version": 1,
    }

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO posted_repositories (
                id, project_id, canonical_repo_key, canonical_repo_url,
                github, hackathon, project_description, source,
                evaluation_snapshot, ranking_snapshot, post_instances,
                posting_state, audit
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (canonical_repo_key) DO UPDATE SET
                github               = EXCLUDED.github,
                hackathon            = EXCLUDED.hackathon,
                project_description  = EXCLUDED.project_description,
                evaluation_snapshot  = EXCLUDED.evaluation_snapshot,
                ranking_snapshot     = EXCLUDED.ranking_snapshot,
                post_instances       = posted_repositories.post_instances || EXCLUDED.post_instances,
                posting_state        = jsonb_set(
                    posted_repositories.posting_state,
                    '{exported_platforms}',
                    EXCLUDED.posting_state -> 'exported_platforms'
                )
            """,
            (
                posted_id,
                candidate.project_id,
                candidate.canonical_repo_key,
                canonical_url,
                Jsonb(github_payload) if github_payload is not None else None,
                Jsonb(hackathon_payload) if hackathon_payload is not None else None,
                Jsonb(project_description),
                Jsonb(source_payload),
                Jsonb(evaluation_snapshot),
                Jsonb(ranking_snapshot),
                Jsonb(post_instances_payload),
                Jsonb(posting_state),
                Jsonb(audit),
            ),
        )
    conn.commit()
    return posted_id


def mark_manually_posted(
    conn: psycopg.Connection,
    *,
    posted_id: str,
    channel: str,
    external_post_url: str | None,
    operator: str = "operator",
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE posted_repositories
            SET post_instances = (
                SELECT jsonb_agg(
                    CASE
                        WHEN inst ->> 'platform' = %s
                        THEN jsonb_set(
                            jsonb_set(
                                inst,
                                '{status}', '"manually_posted"'::jsonb
                            ),
                            '{publication}',
                            jsonb_build_object(
                                'publishing_mode', 'manual',
                                'posted_by', %s,
                                'posted_at', %s,
                                'external_post_url', %s,
                                'external_post_id', null
                            )
                        )
                        ELSE inst
                    END
                )
                FROM jsonb_array_elements(post_instances) inst
            ),
            posting_state = jsonb_set(
                jsonb_set(
                    jsonb_set(posting_state, '{has_been_posted}', 'true'::jsonb),
                    '{last_posted_at}', to_jsonb(%s::text)
                ),
                '{first_posted_at}',
                CASE WHEN posting_state ? 'first_posted_at' AND posting_state ->> 'first_posted_at' IS NOT NULL
                     THEN posting_state -> 'first_posted_at'
                     ELSE to_jsonb(%s::text) END
            )
            WHERE id = %s
            """,
            (channel, operator, now, external_post_url, now, now, posted_id),
        )
    conn.commit()


def _post_instance_for(package: PostPackage) -> dict:
    return {
        "post_id": package.post_id,
        "platform": package.channel,
        "status": "exported",
        "content": package.content.model_dump(mode="json"),
        "media": [_media_dict(asset) for asset in package.media],
        "source_links": package.source_links,
        "review": {"approved_by": None, "approved_at": None, "review_notes": package.review_notes},
        "publication": {
            "publishing_mode": "manual",
            "posted_by": None,
            "posted_at": None,
            "external_post_url": None,
            "external_post_id": None,
        },
    }


def _media_dict(asset: MediaAsset) -> dict:
    return asset.model_dump(mode="json")
