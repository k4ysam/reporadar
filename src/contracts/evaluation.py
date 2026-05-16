from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EvaluationScores(BaseModel):
    """Score rubric (1-10 each). Extra fields are tolerated so new dimensions
    can be added by the evaluator without breaking older readers."""

    model_config = ConfigDict(frozen=True)

    novelty: float = Field(ge=1, le=10)
    explainability: float = Field(ge=1, le=10)
    overall: float = Field(ge=1, le=10)
    usefulness: float | None = None
    developer_relevance: float | None = None
    student_learning_value: float | None = None
    freshness: float | None = None
    visual_post_potential: float | None = None


class Evaluation(BaseModel):
    """LLM evaluation of a single candidate.

    Lives inside the candidate row's `evaluation` JSONB section. See the v2
    architecture doc §3 for the canonical event shape.
    """

    model_config = ConfigDict(frozen=True)

    evaluation_id: str
    candidate_id: str
    project_id: str
    run_id: str
    evaluated_at: datetime
    model: str
    provider: str
    prompt_version: str

    summary: str
    why_interesting: str
    audience: str
    suggested_angle: str | None = None

    scores: EvaluationScores
    skip: bool = False
    skip_reason: str | None = None
    risks: list[str] = Field(default_factory=list)
    evidence_quality: str | None = None

    raw_response: str | None = None
