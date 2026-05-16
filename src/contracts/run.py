from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RunStatus = Literal["running", "completed", "failed"]


class PipelineRun(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str = Field(default_factory=lambda: f"run_{uuid.uuid4()}")
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: RunStatus = "running"
    run_type: str = "daily_discovery"
    requested_by: str = "manual"
    config: dict = Field(default_factory=dict)
