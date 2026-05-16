from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import psycopg

from src.ai_gateway.factory import get_image_provider
from src.common.config import Settings
from src.common.ids import asset_id
from src.content_generation.media.channels import get_profile
from src.contracts.candidate import Candidate
from src.contracts.content import GeneratedContent
from src.contracts.evaluation import Evaluation
from src.contracts.media import MediaAsset, RenderResult


def render_media(
    conn: psycopg.Connection,
    settings: Settings,
    run_id: str,
    candidate: Candidate,
    evaluation: Evaluation,
    content: GeneratedContent,
    *,
    channel: str,
) -> RenderResult:
    """Generate one image asset for `channel` and return its metadata.

    The image binary is written to settings.output_dir; only path + metadata
    are stored on the asset. Per v2 §14 we never store binary in the DB.
    """
    profile = get_profile(channel)
    output_dir = Path(settings.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    image_client = get_image_provider(settings, conn, run_id, size=profile.openai_size)
    prompt = profile.prompt_builder(candidate, evaluation, content)

    stem = _safe_stem(candidate.display_name)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    target = output_dir / f"{channel}_{stem}_{timestamp}.jpg"
    image_client.generate(prompt, target)

    asset = MediaAsset(
        asset_id=asset_id(),
        asset_type="poster",
        channel=channel,
        local_path=str(target),
        width=profile.width,
        height=profile.height,
        aspect_ratio=profile.aspect_ratio,
        alt_text=_alt_text_for(candidate, evaluation, channel),
        image_prompt_version=profile.image_prompt_version,
        generated_at=datetime.now(timezone.utc),
    )
    return RenderResult(channel=channel, assets=[asset])


def _safe_stem(name: str) -> str:
    safe = "".join(c if c.isalnum() or c in ("-", "_") else "-" for c in name).strip("-").lower()
    return safe[:60] or "post"


def _alt_text_for(candidate: Candidate, evaluation: Evaluation, channel: str) -> str:
    short_summary = (evaluation.summary or "").strip().split(".")[0]
    return f"RepoRadar {channel} poster for {candidate.display_name}. {short_summary}."
