from __future__ import annotations

from datetime import datetime, timezone

import psycopg

from src.ai_gateway.llm.base import LLMProvider
from src.candidate_intelligence.enrichment.github_repo import enrich_github_candidate
from src.candidate_intelligence.evaluation.parser import call_with_retry
from src.candidate_intelligence.evaluation.prompts import (
    REPO_PROMPT_VERSION,
    REPO_SYSTEM_PROMPT,
    build_repo_prompt,
)
from src.candidate_intelligence.repository import set_evaluation, upsert_candidate
from src.candidate_intelligence.source_adapters.github_discovery.client import GithubClient
from src.common.ids import evaluation_id
from src.contracts.candidate import Candidate
from src.contracts.evaluation import Evaluation, EvaluationScores


def evaluate_repo(
    candidate: Candidate,
    provider: LLMProvider,
    github_client: GithubClient,
    conn: psycopg.Connection,
) -> Evaluation:
    """Enrich + LLM-evaluate one GitHub candidate, persisting the result."""
    if candidate.github is None:
        raise ValueError(f"Candidate {candidate.candidate_id} has no github snapshot")

    enrichment = enrich_github_candidate(candidate.github.full_name, github_client)
    candidate_with_enrichment = candidate.model_copy(update={"enrichment": enrichment})
    upsert_candidate(conn, candidate_with_enrichment)

    prompt = build_repo_prompt(candidate_with_enrichment, enrichment)
    parsed, raw = call_with_retry(provider, prompt, REPO_SYSTEM_PROMPT)

    scores = EvaluationScores(
        novelty=float(parsed["novelty_score"]),
        explainability=float(parsed["explainability_score"]),
        overall=float(parsed["overall_score"]),
    )
    evaluation = Evaluation(
        evaluation_id=evaluation_id(),
        candidate_id=candidate.candidate_id,
        project_id=candidate.project_id,
        run_id=candidate.run_id,
        evaluated_at=datetime.now(timezone.utc),
        model=provider.model,
        provider=provider.name,
        prompt_version=REPO_PROMPT_VERSION,
        summary=parsed["summary"],
        why_interesting=parsed["why_interesting"],
        audience=parsed["audience"],
        scores=scores,
        skip=bool(parsed.get("skip", False)),
        raw_response=raw,
    )

    set_evaluation(
        conn,
        candidate_id=candidate.candidate_id,
        evaluation_payload=evaluation.model_dump(mode="json"),
        skip=evaluation.skip,
    )
    return evaluation
