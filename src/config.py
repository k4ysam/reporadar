from __future__ import annotations

import os
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel, field_validator, model_validator

load_dotenv()

LLMProviderName = Literal["claude", "gemini", "openai"]


class Settings(BaseModel):
    # --- discovery ---
    gh_token: str
    velocity_window_hours: int = 72
    repo_max_age_days: int = 365
    star_growth_min_pct: float = 50.0
    star_base_min: int = 10
    max_candidates_per_run: int = 15
    devpost_max_projects_per_run: int = 25

    # --- LLM provider ---
    llm_provider: LLMProviderName = "openai"
    anthropic_api_key: str | None = None
    gemini_api_key: str | None = None
    openai_api_key: str | None = None
    claude_model: str = "claude-sonnet-4-6"
    gemini_model: str = "gemini-2.0-flash"
    openai_model: str = "gpt-5.4-mini"
    max_evaluations_per_run: int = 5
    llm_daily_limit: int = 20

    # --- output ---
    db_path: str = "reporadar.db"
    output_dir: str = "output"

    # --- image hosting ---
    image_host_endpoint: str | None = None  # e.g. https://<accountid>.r2.cloudflarestorage.com (R2) or empty for AWS
    image_host_bucket: str | None = None
    image_host_region: str = "auto"
    image_host_public_base_url: str | None = None  # public read URL prefix
    image_host_access_key: str | None = None
    image_host_secret_key: str | None = None

    # --- instagram ---
    ig_access_token: str | None = None
    ig_business_account_id: str | None = None
    ig_app_id: str | None = None
    ig_app_secret: str | None = None
    ig_dry_run: bool = False

    # --- scheduling ---
    schedule_hour: int = 6  # local time hour to fire pipeline
    schedule_jitter_minutes: int = 15  # ±15 min per PRD
    timezone_name: str = "UTC"

    # --- legacy aliases retained for tests ---
    @property
    def llm_model(self) -> str:
        if self.llm_provider == "claude":
            return self.claude_model
        if self.llm_provider == "openai":
            return self.openai_model
        return self.gemini_model

    @property
    def gemini_daily_limit(self) -> int:
        return self.llm_daily_limit

    @field_validator("gh_token")
    @classmethod
    def gh_token_required(cls, v: str, info) -> str:
        if not v:
            raise ValueError("gh_token must not be empty")
        return v

    @model_validator(mode="after")
    def provider_key_present(self) -> "Settings":
        if self.llm_provider == "claude" and not self.anthropic_api_key:
            raise ValueError("LLM_PROVIDER=claude requires ANTHROPIC_API_KEY")
        if self.llm_provider == "gemini" and not self.gemini_api_key:
            raise ValueError("LLM_PROVIDER=gemini requires GEMINI_API_KEY")
        if self.llm_provider == "openai" and not self.openai_api_key:
            raise ValueError("LLM_PROVIDER=openai requires OPENAI_API_KEY")
        return self

    @classmethod
    def from_env(cls) -> "Settings":
        provider_raw = os.environ.get("LLM_PROVIDER", "openai").lower().strip()
        if provider_raw not in ("claude", "gemini", "openai"):
            raise RuntimeError(
                f"LLM_PROVIDER must be 'claude', 'gemini', or 'openai' (got {provider_raw!r})"
            )

        if not os.environ.get("GH_TOKEN"):
            raise RuntimeError(
                "Missing required environment variable: GH_TOKEN.\n"
                "Copy .env.template to .env and fill in the values."
            )

        return cls(
            gh_token=os.environ["GH_TOKEN"],
            velocity_window_hours=int(os.environ.get("VELOCITY_WINDOW_HOURS", "72")),
            repo_max_age_days=int(os.environ.get("REPO_MAX_AGE_DAYS", "365")),
            star_growth_min_pct=float(os.environ.get("STAR_GROWTH_MIN_PCT", "50")),
            star_base_min=int(os.environ.get("STAR_BASE_MIN", "10")),
            max_candidates_per_run=int(os.environ.get("MAX_CANDIDATES_PER_RUN", "15")),
            devpost_max_projects_per_run=int(os.environ.get("DEVPOST_MAX_PROJECTS_PER_RUN", "25")),

            llm_provider=provider_raw,
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
            gemini_api_key=os.environ.get("GEMINI_API_KEY"),
            openai_api_key=os.environ.get("OPENAI_API_KEY"),
            claude_model=os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6"),
            gemini_model=os.environ.get("GEMINI_MODEL") or os.environ.get("LLM_MODEL", "gemini-2.0-flash"),
            openai_model=os.environ.get("OPENAI_MODEL") or os.environ.get("LLM_MODEL", "gpt-5.4-mini"),
            max_evaluations_per_run=int(os.environ.get("MAX_EVALUATIONS_PER_RUN", "5")),
            llm_daily_limit=int(
                os.environ.get("LLM_DAILY_LIMIT")
                or os.environ.get("GEMINI_DAILY_LIMIT", "20")
            ),

            db_path=os.environ.get("DB_PATH", "reporadar.db"),
            output_dir=os.environ.get("OUTPUT_DIR", "output"),

            image_host_endpoint=os.environ.get("IMAGE_HOST_ENDPOINT") or None,
            image_host_bucket=os.environ.get("IMAGE_HOST_BUCKET") or None,
            image_host_region=os.environ.get("IMAGE_HOST_REGION", "auto"),
            image_host_public_base_url=os.environ.get("IMAGE_HOST_PUBLIC_BASE_URL") or None,
            image_host_access_key=os.environ.get("IMAGE_HOST_ACCESS_KEY") or None,
            image_host_secret_key=os.environ.get("IMAGE_HOST_SECRET_KEY") or None,

            ig_access_token=os.environ.get("IG_ACCESS_TOKEN") or None,
            ig_business_account_id=os.environ.get("IG_BUSINESS_ACCOUNT_ID") or None,
            ig_app_id=os.environ.get("IG_APP_ID") or None,
            ig_app_secret=os.environ.get("IG_APP_SECRET") or None,
            ig_dry_run=os.environ.get("IG_DRY_RUN", "0") in ("1", "true", "True"),

            schedule_hour=int(os.environ.get("SCHEDULE_HOUR", "6")),
            schedule_jitter_minutes=int(os.environ.get("SCHEDULE_JITTER_MINUTES", "15")),
            timezone_name=os.environ.get("TIMEZONE", "UTC"),
        )
