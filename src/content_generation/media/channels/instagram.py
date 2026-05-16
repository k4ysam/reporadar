"""Instagram media profile + prompt builder.

Square 1024×1024 poster. Two variants depending on whether the candidate
is a GitHub repo or a hackathon project — both produce the same aspect.
"""
from __future__ import annotations

from src.content_generation.media.profile import ChannelMediaProfile
from src.content_generation.media.style import (
    BASE_STYLE,
    BRAND,
    headline_from_content,
    imagery_for_hackathon,
    imagery_for_repo,
    short_summary,
)
from src.contracts.candidate import Candidate
from src.contracts.content import GeneratedContent
from src.contracts.evaluation import Evaluation


def build_instagram_image_prompt(
    candidate: Candidate,
    evaluation: Evaluation,
    content: GeneratedContent,
) -> str:
    if candidate.github:
        return _repo_variant(candidate, evaluation, content)
    return _hackathon_variant(candidate, evaluation, content)


def _repo_variant(
    candidate: Candidate,
    evaluation: Evaluation,
    content: GeneratedContent,
) -> str:
    gh = candidate.github
    full_name = gh.full_name if gh else candidate.display_name
    repo_short = full_name.split("/")[-1]
    sub_context_parts = [full_name]
    if gh and gh.primary_language:
        sub_context_parts.append(gh.primary_language)
    sub_context = "  ·  ".join(sub_context_parts)

    imagery = imagery_for_repo(evaluation, gh.primary_language if gh else None)
    headline = headline_from_content(content, evaluation.summary)
    return (
        f"{BASE_STYLE}\n\n"
        f"Aspect: Instagram square (1:1).\n\n"
        f"Imagery: {imagery}. The visual should evoke the project's purpose "
        f"({short_summary(evaluation.summary)}).\n\n"
        f'Headline (large, all-caps, sans-serif, top-center): "{headline}"\n'
        f'Sub-context (small, bottom-left, single line): "{sub_context}"\n'
        f'Brand mark (small, bottom-right, single line): "{BRAND}"\n\n'
        f"Subject hint: open-source project named {repo_short}."
    )


def _hackathon_variant(
    candidate: Candidate,
    evaluation: Evaluation,
    content: GeneratedContent,
) -> str:
    h = candidate.hackathon
    sub_context_parts: list[str] = []
    if h and h.hackathon_name:
        sub_context_parts.append(h.hackathon_name)
    if h and h.prize:
        sub_context_parts.append(h.prize)
    sub_context = "  ·  ".join(sub_context_parts) or (
        h.project_name if h else candidate.display_name
    )

    imagery = imagery_for_hackathon(evaluation, h.technologies if h else [])
    headline = headline_from_content(content, evaluation.summary)
    project_name = h.project_name if h else candidate.display_name

    return (
        f"{BASE_STYLE}\n\n"
        f"Aspect: Instagram square (1:1). Hackathon winner spotlight.\n\n"
        f"Imagery: {imagery}. The visual should evoke the project's purpose "
        f"({short_summary(evaluation.summary)}).\n\n"
        f'Headline (large, all-caps, sans-serif, top-center): "{headline}"\n'
        f'Sub-context (small, bottom-left, single line): "{sub_context}"\n'
        f'Brand mark (small, bottom-right, single line): "{BRAND}"\n\n'
        f"Subject hint: hackathon project named {project_name}."
    )


INSTAGRAM_PROFILE = ChannelMediaProfile(
    channel="instagram",
    width=1024,
    height=1024,
    aspect_ratio="1:1",
    openai_size="1024x1024",
    image_prompt_version="instagram_square_v3",
    prompt_builder=build_instagram_image_prompt,
    style="stop-scroll developer poster",
)
