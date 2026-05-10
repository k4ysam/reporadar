from __future__ import annotations

import re
from pathlib import Path

from src.caption.linkedin import generate_repo_linkedin_commentary
from src.llm.provider import LLMProvider
from src.models import Evaluation, LinkedInPostPackage
from src.render.image_gen import OpenAIImageClient
from src.render.renderer import render_linkedin_repo_poster


def _shorten(text: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", text.strip())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def build_repo_poster_headline(evaluation: Evaluation) -> str:
    short = evaluation.full_name.split("/")[-1]
    summary = evaluation.summary.strip().rstrip(".")
    if summary:
        headline = summary if short.lower() in summary.lower() else f"{short}: {summary}"
    else:
        headline = f"{short} is rising fast on GitHub"
    return _shorten(headline, 92)


def build_repo_alt_text(evaluation: Evaluation, headline: str) -> str:
    stars = (
        f"{evaluation.stars_48h} stars added"
        if evaluation.stars_48h
        else "GitHub growth signal"
    )
    growth = (
        f"{int(evaluation.growth_pct)} percent growth"
        if evaluation.growth_pct
        else "growth tracked by RepoRadar"
    )
    return (
        f"RepoRadar poster for {evaluation.full_name}. "
        f"Headline: {headline}. "
        f"Shows {stars} and {growth}."
    )


def build_repo_linkedin_package(
    evaluation: Evaluation,
    provider: LLMProvider,
    image_client: OpenAIImageClient,
    output_dir: str | Path,
    *,
    language: str | None = None,
    topics: list[str] | None = None,
    window_hours: int = 72,
) -> LinkedInPostPackage:
    repo_url = f"https://github.com/{evaluation.full_name}"
    commentary = generate_repo_linkedin_commentary(
        evaluation,
        provider,
        repo_url=repo_url,
        language=language,
        topics=topics,
    )
    headline = build_repo_poster_headline(evaluation)
    render = render_linkedin_repo_poster(
        evaluation,
        output_dir,
        image_client,
        headline=headline,
        language=language,
        topics=topics,
        window_hours=window_hours,
    )
    return LinkedInPostPackage(
        commentary=commentary,
        image_paths=list(render.paths),
        alt_text=build_repo_alt_text(evaluation, headline),
        repo_url=repo_url,
        source_name=evaluation.full_name,
    )
