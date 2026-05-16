from __future__ import annotations

import re
from datetime import datetime, timezone

from src.ai_gateway.llm.base import LLMProvider
from src.contracts.candidate import Candidate
from src.contracts.content import GeneratedContent
from src.contracts.evaluation import Evaluation

PROMPT_VERSION = "linkedin_repo_v4"
CHAR_LIMIT = 3000

_SYSTEM = """You write LinkedIn posts for RepoRadar, a developer discovery account.

Voice:
- Plain, specific, technical, and curious.
- No corporate-speak, no hype words like revolutionary or game-changing.

Structure:
1. Open with the repo/project and a specific surprising capability.
2. Explain what it is and why developers are paying attention.
3. Explain how it works in plain technical language.
4. Use only proof provided in the prompt: stars, growth, language, summary, or stated repo context.
5. Include a caveat if evidence is thin, early, unverified, or README-reported.
6. End with one comment-driving question and a RepoRadar follow CTA.

Constraints:
- 900-1800 characters.
- 3-5 hashtags max.
- Do not invent benchmark numbers, licenses, companies, maintainers, or launch dates.
- Return the LinkedIn post text only. No markdown fences, no JSON."""


def generate_linkedin_commentary(
    candidate: Candidate,
    evaluation: Evaluation,
    provider: LLMProvider,
) -> GeneratedContent:
    if not candidate.github:
        raise ValueError(
            "LinkedIn commentary currently only supports GitHub repos. "
            "Hackathon submissions go through the Instagram caption path."
        )

    gh = candidate.github
    stars_line = (
        f"{candidate.discovery.star_delta} stars added in the tracked window"
        if candidate.discovery and candidate.discovery.star_delta
        else "stars: unavailable"
    )
    growth = (
        f"+{candidate.discovery.growth_percent:.0f}%"
        if candidate.discovery and candidate.discovery.growth_percent
        else "growth: unavailable"
    )
    prompt = (
        f"Repo: {gh.full_name}\n"
        f"GitHub URL: {gh.url}\n"
        f"Language: {gh.primary_language or 'unknown'}\n"
        f"Topics: {', '.join(gh.topics) or 'none provided'}\n"
        f"Stars signal: {stars_line}\n"
        f"Growth signal: {growth}\n"
        f"Editorial summary: {evaluation.summary}\n"
        f"Why interesting: {evaluation.why_interesting}\n"
        f"Audience: {evaluation.audience}\n"
    )

    raw = provider.generate(prompt, system=_SYSTEM)
    text = _clean(raw)
    if not text:
        raw = provider.generate(
            prompt + "\n\nReturn a complete LinkedIn post. Do not return an empty response.",
            system=_SYSTEM,
        )
        text = _clean(raw)
    if not text:
        raise ValueError("LinkedIn commentary generation returned empty text")

    text = text[:CHAR_LIMIT].rstrip()

    return GeneratedContent(
        channel="linkedin",
        content_format="commentary",
        text=text,
        source_links=[gh.url],
        character_count=len(text),
        generated_at=datetime.now(timezone.utc),
        model=provider.model,
        prompt_version=PROMPT_VERSION,
    )


def _clean(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:text|markdown)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text.strip())
    return text
