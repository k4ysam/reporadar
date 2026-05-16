from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MediaType = Literal["poster", "thumbnail", "header", "carousel_slide"]


class MediaAsset(BaseModel):
    """One generated image asset. The binary lives on disk (settings.output_dir);
    only the path + metadata is persisted."""

    model_config = ConfigDict(frozen=True)

    asset_id: str
    asset_type: MediaType = "poster"
    channel: str
    local_path: str
    uri: str | None = None
    mime_type: str = "image/jpeg"
    width: int
    height: int
    aspect_ratio: str
    alt_text: str | None = None
    image_prompt_version: str
    generated_by: str = "openai_image"
    generated_at: datetime
    content_hash: str | None = None


class RenderResult(BaseModel):
    """Aggregate of all assets produced for one channel render."""

    model_config = ConfigDict(frozen=True)

    channel: str
    assets: list[MediaAsset] = Field(default_factory=list)

    @property
    def paths(self) -> list[str]:
        return [a.local_path for a in self.assets]
