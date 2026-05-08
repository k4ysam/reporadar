from __future__ import annotations

import re

from src.llm.provider import LLMProvider
from src.models import Evaluation

_REPO_LINKEDIN_SYSTEM = """You write LinkedIn posts for RepoRadar, a developer discovery account.

Voice:
- Plain, specific, technical, and curious.
- Similar structure to high-performing tech news pages, but with stricter evidence.
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
- If stars are unavailable, do not pretend they are known.
- Return the LinkedIn post text only. No markdown fences, no JSON."""


def _clean_commentary(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:text|markdown)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text.strip())
    return text


def _format_topics(topics: list[str] | None) -> str:
    if not topics:
        return "none provided"
    return ", ".join(t for t in topics if t) or "none provided"


def generate_repo_linkedin_commentary(
    evaluation: Evaluation,
    provider: LLMProvider,
    *,
    repo_url: str,
    language: str | None = None,
    topics: list[str] | None = None,
) -> str:
    stars = (
        f"{evaluation.stars_48h} stars added in the tracked window"
        if evaluation.stars_48h
        else "unavailable from persisted evaluation"
    )
    growth = f"+{evaluation.growth_pct:.0f}%" if evaluation.growth_pct else "unavailable"
    prompt = (
        f"Repo: {evaluation.full_name}\n"
        f"GitHub URL: {repo_url}\n"
        f"Language: {language or 'unknown'}\n"
        f"Topics: {_format_topics(topics)}\n"
        f"Stars signal: {stars}\n"
        f"Growth signal: {growth}\n"
        f"Editorial summary: {evaluation.summary}\n"
        f"Why interesting: {evaluation.why_interesting}\n"
        f"Audience: {evaluation.audience}\n"
    )

    raw = provider.generate(prompt, system=_REPO_LINKEDIN_SYSTEM)
    text = _clean_commentary(raw)
    if not text:
        raw = provider.generate(
            prompt + "\n\nReturn a complete LinkedIn post. Do not return an empty response.",
            system=_REPO_LINKEDIN_SYSTEM,
        )
        text = _clean_commentary(raw)
    if not text:
        raise ValueError("LinkedIn commentary generation returned empty text")
    return text[:3000].rstrip()
