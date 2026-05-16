from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RankingBreakdown(BaseModel):
    """Per-candidate score components. Persisted so future selections can be
    audited even if the ranking algorithm changes."""

    model_config = ConfigDict(frozen=True)

    evaluation_overall_score: float = 0.0
    novelty_score: float = 0.0
    explainability_score: float = 0.0
    audience_fit_score: float = 0.0
    freshness_bonus: float = 0.0
    weak_evidence_penalty: float = 0.0
    already_posted_penalty: float = 0.0


class SelectionDecision(BaseModel):
    """Output of the Selection service for one candidate."""

    model_config = ConfigDict(frozen=True)

    selection_id: str
    candidate_id: str
    project_id: str
    run_id: str
    ranking_version: str
    ranking_score: float
    rank_in_run: int
    total_candidates_in_run: int
    score_breakdown: RankingBreakdown
    ranking_reasons: list[str] = Field(default_factory=list)
    eligible: bool = True
    selected: bool = False
    selected_for_channels: list[str] = Field(default_factory=list)
    selected_at: datetime | None = None
    not_selected_reason: str | None = None
