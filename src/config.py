from __future__ import annotations

import os

from dotenv import load_dotenv
from pydantic import BaseModel, field_validator

load_dotenv()


class Settings(BaseModel):
    gh_token: str
    anthropic_api_key: str
    anthropic_model: str = "claude-sonnet-4-6"
    db_path: str = "reporadar.db"
    max_candidates_per_run: int = 15
    max_evaluations_per_run: int = 5
    star_growth_min_pct: float = 200.0
    star_base_min: int = 20
    velocity_window_hours: int = 48

    @field_validator("gh_token", "anthropic_api_key")
    @classmethod
    def must_be_set(cls, v: str, info) -> str:
        if not v:
            raise ValueError(f"{info.field_name} must not be empty")
        return v

    @classmethod
    def from_env(cls) -> "Settings":
        missing = [k for k in ("GH_TOKEN", "ANTHROPIC_API_KEY") if not os.environ.get(k)]
        if missing:
            raise RuntimeError(
                f"Missing required environment variables: {', '.join(missing)}\n"
                "Copy .env.template to .env and fill in the values."
            )
        return cls(
            gh_token=os.environ["GH_TOKEN"],
            anthropic_api_key=os.environ["ANTHROPIC_API_KEY"],
            anthropic_model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
            db_path=os.environ.get("DB_PATH", "reporadar.db"),
            max_candidates_per_run=int(os.environ.get("MAX_CANDIDATES_PER_RUN", "15")),
            max_evaluations_per_run=int(os.environ.get("MAX_EVALUATIONS_PER_RUN", "5")),
            star_growth_min_pct=float(os.environ.get("STAR_GROWTH_MIN_PCT", "200")),
            star_base_min=int(os.environ.get("STAR_BASE_MIN", "20")),
            velocity_window_hours=int(os.environ.get("VELOCITY_WINDOW_HOURS", "48")),
        )
