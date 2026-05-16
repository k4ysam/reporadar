from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.contracts.content import GeneratedContent
from src.contracts.media import MediaAsset

PostStatus = Literal[
    "drafted",
    "ready_for_review",
    "approved",
    "rejected",
    "regenerate_requested",
    "exported",
    "manually_posted",
    "published",
    "failed",
    "archived",
]


class PostPackage(BaseModel):
    """Final channel-ready package handed to publishing / review."""

    model_config = ConfigDict(frozen=True)

    post_id: str
    project_id: str
    candidate_id: str
    run_id: str
    channel: str
    status: PostStatus = "ready_for_review"
    content: GeneratedContent
    media: list[MediaAsset] = Field(default_factory=list)
    source_links: list[str] = Field(default_factory=list)
    review_notes: str | None = None
    created_at: datetime
