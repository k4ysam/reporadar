from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Channel = Literal["instagram", "linkedin", "newsletter", "x", "website"]
ContentFormat = Literal["caption", "commentary", "thread", "email_blurb"]


class GeneratedContent(BaseModel):
    """Channel-specific generated text. Owned by content_generation service."""

    model_config = ConfigDict(frozen=True)

    channel: Channel
    content_format: ContentFormat
    text: str
    hook: str | None = None
    body: str | None = None
    cta: str | None = None
    hashtags: list[str] = Field(default_factory=list)
    source_links: list[str] = Field(default_factory=list)
    character_count: int = 0
    generated_at: datetime
    model: str
    prompt_version: str
    content_version: int = 1
