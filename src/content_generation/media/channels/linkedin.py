"""LinkedIn media profile + prompt builder.

Tall 1024×1536 poster (2:3). Currently only supports GitHub candidates;
hackathon variant can be added by extending `build_linkedin_image_prompt`
in parallel with the Instagram profile.
"""
from __future__ import annotations

from src.content_generation.media.profile import ChannelMediaProfile
from src.content_generation.media.style import (
    BASE_STYLE,
    BRAND,
    headline_from_content,
    imagery_for_repo,
    short_summary,
)
from src.contracts.candidate import Candidate
from src.contracts.content import GeneratedContent
from src.contracts.evaluation import Evaluation


def build_linkedin_image_prompt(
    candidate: Candidate,
    evaluation: Evaluation,
    content: GeneratedContent,
) -> str:
    if not candidate.github:
        raise ValueError("LinkedIn poster currently only supports GitHub candidates")

    gh = candidate.github
    sub_context_parts = [gh.full_name]
    if gh.primary_language:
        sub_context_parts.append(gh.primary_language)
    topics = (gh.topics or [])[:3]
    sub_context = "  ·  ".join(sub_context_parts)
    topic_line = "  ·  ".join(topics) if topics else ""

    stats_parts: list[str] = []
    if candidate.discovery and candidate.discovery.star_delta:
        stats_parts.append(f"+{candidate.discovery.star_delta} STARS")
    if candidate.discovery and candidate.discovery.growth_percent:
        stats_parts.append(f"+{int(candidate.discovery.growth_percent)}% GROWTH")
    stats_line = "  ·  ".join(stats_parts) if stats_parts else "TRACKED ON GITHUB"

    imagery = imagery_for_repo(evaluation, gh.primary_language)
    headline = headline_from_content(content, evaluation.summary, max_len=110)

    return (
        f"{BASE_STYLE}\n\n"
        f"Aspect: tall LinkedIn poster (2:3). Headline fills upper third; stats band sits in the lower third.\n\n"
        f"Imagery: {imagery}. The visual should evoke the project's purpose "
        f"({short_summary(evaluation.summary)}).\n\n"
        f'Headline (very large, all-caps, sans-serif, top-center, multi-line allowed): "{headline}"\n'
        f'Stats band (smaller, mid-bottom, single line, all-caps): "{stats_line}"\n'
        f'Sub-context (small, bottom-left, single line): "{sub_context}"\n'
        + (f'Topic badges (small, lower band, comma-separated): "{topic_line}"\n' if topic_line else "")
        + f'Brand mark (small, bottom-right, single line): "{BRAND}"\n\n'
        f"Subject hint: open-source project named {gh.repo}."
    )


LINKEDIN_PROFILE = ChannelMediaProfile(
    channel="linkedin",
    width=1024,
    height=1536,
    aspect_ratio="2:3",
    openai_size="1024x1536",
    image_prompt_version="linkedin_poster_v3",
    prompt_builder=build_linkedin_image_prompt,
    style="professional technical poster",
)
