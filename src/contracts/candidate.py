from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SourceType = Literal["github_discovery", "devpost_discovery", "manual_submission"]


class CandidateSource(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_type: SourceType
    source_name: str
    source_url: str
    discovered_at: datetime
    discovery_reason: str | None = None
    manual_submission: dict | None = None


class DiscoverySignals(BaseModel):
    model_config = ConfigDict(frozen=True)

    stars_at_discovery: int = 0
    stars_window_ago: int = 0
    star_delta: int = 0
    growth_percent: float = 0.0
    window_hours: int = 72
    commit_count_7d: int = 0
    pushed_recently: bool = False


class GithubSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    owner: str
    repo: str
    full_name: str
    url: str
    description: str | None = None
    homepage_url: str | None = None
    primary_language: str | None = None
    topics: list[str] = Field(default_factory=list)
    license: str | None = None
    stars_count: int = 0
    forks_count: int = 0
    open_issues_count: int = 0
    watchers_count: int = 0
    default_branch: str | None = None
    created_at: datetime | None = None
    pushed_at: datetime | None = None
    archived: bool = False
    is_fork: bool = False
    github_repo_id: int | None = None


class HackathonSnapshot(BaseModel):
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
    description: str | None = None
    technologies: list[str] = Field(default_factory=list)


class RepoEnrichment(BaseModel):
    """Output of the enrichment stage: README + activity + signals."""

    model_config = ConfigDict(frozen=True)

    readme: str | None = None
    readme_summary: str | None = None
    has_installation_instructions: bool = False
    has_usage_examples: bool = False
    recent_commits: list[str] = Field(default_factory=list)
    top_issues: list[str] = Field(default_factory=list)
    contributors_count: int = 0
    latest_commit_at: datetime | None = None


class Candidate(BaseModel):
    """In-memory candidate flowing between services for one run."""

    model_config = ConfigDict(frozen=True)

    candidate_id: str
    project_id: str
    canonical_repo_key: str
    run_id: str
    source: CandidateSource
    discovery: DiscoverySignals | None = None
    github: GithubSnapshot | None = None
    hackathon: HackathonSnapshot | None = None
    enrichment: RepoEnrichment | None = None
    already_posted: bool = False

    @property
    def display_name(self) -> str:
        if self.github:
            return self.github.full_name
        if self.hackathon:
            return self.hackathon.project_name
        return self.canonical_repo_key
