from __future__ import annotations

import os

from dotenv import load_dotenv
from pydantic import BaseModel, field_validator

load_dotenv()


class Settings(BaseModel):
    gh_token: str
    gemini_api_key: str
    llm_model: str = "gemini-2.0-flash"
    db_path: str = "reporadar.db"
    max_candidates_per_run: int = 15
    max_evaluations_per_run: int = 5
    gemini_daily_limit: int = 20
    repo_max_age_days: int = 365
    star_growth_min_pct: float = 200.0
    star_base_min: int = 20
    velocity_window_hours: int = 48

    @field_validator("gh_token", "gemini_api_key")
    @classmethod
    def must_be_set(cls, v: str, info) -> str:
        if not v:
            raise ValueError(f"{info.field_name} must not be empty")
        return v

    @classmethod
    def from_env(cls) -> "Settings":
        missing = [k for k in ("GH_TOKEN", "GEMINI_API_KEY") if not os.environ.get(k)]
        if missing:
            raise RuntimeError(
                f"Missing required environment variables: {', '.join(missing)}\n"
                "Copy .env.template to .env and fill in the values."
            )
        return cls(
            gh_token=os.environ["GH_TOKEN"],
            gemini_api_key=os.environ["GEMINI_API_KEY"],
            llm_model=os.environ.get("LLM_MODEL", "gemini-2.0-flash"),
            db_path=os.environ.get("DB_PATH", "reporadar.db"),
            max_candidates_per_run=int(os.environ.get("MAX_CANDIDATES_PER_RUN", "15")),
            max_evaluations_per_run=int(os.environ.get("MAX_EVALUATIONS_PER_RUN", "5")),
            gemini_daily_limit=int(os.environ.get("GEMINI_DAILY_LIMIT", "20")),
            repo_max_age_days=int(os.environ.get("REPO_MAX_AGE_DAYS", "365")),
            star_growth_min_pct=float(os.environ.get("STAR_GROWTH_MIN_PCT", "200")),
            star_base_min=int(os.environ.get("STAR_BASE_MIN", "20")),
            velocity_window_hours=int(os.environ.get("VELOCITY_WINDOW_HOURS", "48")),
        )
