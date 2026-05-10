from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ContentType = Literal["repo", "hackathon"]
MediaType = Literal["single", "carousel"]
PostStatus = Literal["pending", "rendered", "failed"]


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


class HackathonCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)

    devpost_url: str
    project_name: str
    tagline: str | None = None
    hackathon_name: str | None = None
    prize: str | None = None
    team: str | None = None
    github_url: str | None = None
    demo_url: str | None = None
    submitted_at: datetime | None = None
    first_seen_at: datetime
    description: str | None = None
    technologies: list[str] = Field(default_factory=list)


class Evaluation(BaseModel):
    model_config = ConfigDict(frozen=True)

    content_type: ContentType = "repo"
    repo_id: int | None = None
    hackathon_id: int | None = None
    full_name: str  # repo full_name or project_name for hackathon
    summary: str
    why_interesting: str
    audience: str
    novelty_score: float = Field(ge=1, le=10)
    explainability_score: float = Field(ge=1, le=10)
    overall_score: float = Field(ge=1, le=10)
    skip: bool = False
    stars_48h: int = 0
    growth_pct: float = 0.0
    llm_provider: str | None = None


class Caption(BaseModel):
    model_config = ConfigDict(frozen=True)

    hook: str
    body: str
    cta: str
    hashtags: list[str] = Field(default_factory=list)
    source_links: list[str] = Field(default_factory=list)

    def render(self) -> str:
        tag_line = " ".join(f"#{h.lstrip('#')}" for h in self.hashtags if h.strip())
        links = [link.strip() for link in self.source_links if link.strip()]
        sections = [part.strip() for part in (self.hook, self.body, self.cta) if part.strip()]
        if tag_line:
            sections.append(tag_line)
        if links:
            sections.append("Links:\n" + "\n".join(links))
        text = "\n\n".join(sections)
        return text[:2200]


class RenderResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    media_type: MediaType
    paths: list[str]


class SavedPost(BaseModel):
    model_config = ConfigDict(frozen=True)

    post_id: int
    card_paths: list[str]
    caption: str


class LinkedInPostPackage(BaseModel):
    model_config = ConfigDict(frozen=True)

    commentary: str
    image_paths: list[str] = Field(default_factory=list)
    alt_text: str
    repo_url: str
    source_name: str


class PipelineRun(BaseModel):
    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: Literal["running", "completed", "failed"] = "running"
