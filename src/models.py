from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Candidate(BaseModel):
    model_config = ConfigDict(frozen=True)

    repo_id: int
    full_name: str
    description: str | None = None
    stars_now: int
    stars_48h_ago: int
    growth_pct: float
    language: str | None = None
    topics: list[str] = Field(default_factory=list)
    created_at: datetime
    first_seen_at: datetime


class Evaluation(BaseModel):
    model_config = ConfigDict(frozen=True)

    repo_id: int
    full_name: str
    summary: str
    why_interesting: str
    audience: str
    novelty_score: float = Field(ge=1, le=10)
    explainability_score: float = Field(ge=1, le=10)
    overall_score: float = Field(ge=1, le=10)
    stars_48h: int
    growth_pct: float


class PipelineRun(BaseModel):
    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: Literal["running", "completed", "failed"] = "running"
