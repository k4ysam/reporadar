from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from src.models import Caption, Evaluation, HackathonCandidate, RenderResult
from src.render.image_gen import OpenAIImageClient
from src.render.image_prompt import (
    build_hackathon_image_prompt,
    build_linkedin_repo_image_prompt,
    build_repo_image_prompt,
)


def _ensure_output_dir(output_dir: str | Path) -> Path:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    return out


def _safe_stem(name: str) -> str:
    safe = "".join(c if c.isalnum() or c in ("-", "_") else "-" for c in name).strip("-").lower()
    return safe[:60] or "post"


def render_repo_card(
    evaluation: Evaluation,
    caption: Caption,
    output_dir: str | Path,
    image_client: OpenAIImageClient,
    *,
    window_hours: int = 72,
    language: str | None = None,
    file_stem: str | None = None,
) -> RenderResult:
    out = _ensure_output_dir(output_dir)
    prompt = build_repo_image_prompt(evaluation, caption, language=language)

    stem = file_stem or _safe_stem(evaluation.full_name)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    target = out / f"repo_{stem}_{timestamp}.jpg"
    image_client.generate(prompt, target)
    return RenderResult(media_type="single", paths=[str(target)])


def render_hackathon_card(
    evaluation: Evaluation,
    candidate: HackathonCandidate,
    caption: Caption,
    output_dir: str | Path,
    image_client: OpenAIImageClient,
    *,
    file_stem: str | None = None,
) -> RenderResult:
    out = _ensure_output_dir(output_dir)
    prompt = build_hackathon_image_prompt(evaluation, candidate, caption)

    stem = file_stem or _safe_stem(candidate.project_name)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    target = out / f"hackathon_{stem}_{timestamp}.jpg"
    image_client.generate(prompt, target)
    return RenderResult(media_type="single", paths=[str(target)])


def render_linkedin_repo_poster(
    evaluation: Evaluation,
    output_dir: str | Path,
    image_client: OpenAIImageClient,
    *,
    headline: str,
    language: str | None = None,
    topics: list[str] | None = None,
    window_hours: int = 72,
    file_stem: str | None = None,
) -> RenderResult:
    """Tall LinkedIn-aspect poster (1024x1536) generated via OpenAI gpt-image-1.

    The image_client should be configured with size='1024x1536' for proper
    LinkedIn aspect; callers in src/cli.py do this.
    """
    out = _ensure_output_dir(output_dir)
    prompt = build_linkedin_repo_image_prompt(
        evaluation,
        headline=headline,
        language=language,
        topics=topics,
    )

    stem = file_stem or _safe_stem(evaluation.full_name)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    target = out / f"linkedin_repo_{stem}_{timestamp}.jpg"
    image_client.generate(prompt, target)
    return RenderResult(media_type="single", paths=[str(target)])
