from __future__ import annotations

from datetime import datetime, timezone

import psycopg

from src.ai_gateway.llm.base import LLMProvider
from src.candidate_intelligence.evaluation.parser import call_with_retry
from src.candidate_intelligence.evaluation.prompts import (
    HACKATHON_PROMPT_VERSION,
    HACKATHON_SYSTEM_PROMPT,
    build_hackathon_prompt,
)
from src.candidate_intelligence.repository import set_evaluation
from src.common.ids import evaluation_id
from src.contracts.candidate import Candidate
from src.contracts.evaluation import Evaluation, EvaluationScores


def evaluate_hackathon(
    candidate: Candidate,
    provider: LLMProvider,
    conn: psycopg.Connection,
) -> Evaluation:
    """LLM-evaluate one Devpost hackathon candidate, persisting the result."""
    prompt = build_hackathon_prompt(candidate)
    parsed, raw = call_with_retry(provider, prompt, HACKATHON_SYSTEM_PROMPT)

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
        prompt_version=HACKATHON_PROMPT_VERSION,
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
