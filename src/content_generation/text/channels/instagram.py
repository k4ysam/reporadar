from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from src.ai_gateway.llm.base import LLMProvider
from src.contracts.candidate import Candidate
from src.contracts.content import GeneratedContent
from src.contracts.evaluation import Evaluation

REPO_PROMPT_VERSION = "instagram_repo_caption_v3"
HACKATHON_PROMPT_VERSION = "instagram_hackathon_caption_v3"
CHAR_LIMIT = 2200

_REPO_SYSTEM = """You write short, punchy Instagram captions for RepoRadar, a dev-discovery account. \
Voice: confident, opinionated, never breathless. No corporate-speak, no emoji spam. One emoji max.

Constraints:
- hook: ≤80 chars, one catchy summary line.
- body: 2–4 short sentences (≤500 chars total). Concrete, specific, technical when warranted. Do not repeat the hook.
- cta: one short line.
- hashtags: 5–8 lowercase tags, no '#'. Mix broad + specific.
- Do not include URLs in hook, body, cta, or hashtags.

Return ONLY valid JSON: {"hook": "...", "body": "...", "cta": "...", "hashtags": ["..."]}"""

_HACKATHON_SYSTEM = """You write Instagram captions for RepoRadar's hackathon spotlight. \
Tone: punchy, builder-respecting, never condescending. One emoji max.

Constraints:
- hook: ≤80 chars. Lead with the *what* + the constraint.
- body: 2–4 sentences (≤500 chars). What it does, why it's impressive given the time.
- cta: short.
- hashtags: 5–8 lowercase, no '#'.
- Do not include URLs.

Return ONLY valid JSON: {"hook": "...", "body": "...", "cta": "...", "hashtags": ["..."]}"""


def generate_instagram_caption(
    candidate: Candidate,
    evaluation: Evaluation,
    provider: LLMProvider,
) -> GeneratedContent:
    if candidate.github:
        prompt, system, prompt_version = (
            _build_repo_prompt(candidate, evaluation),
            _REPO_SYSTEM,
            REPO_PROMPT_VERSION,
        )
    else:
        prompt, system, prompt_version = (
            _build_hackathon_prompt(candidate, evaluation),
            _HACKATHON_SYSTEM,
            HACKATHON_PROMPT_VERSION,
        )

    parsed = _call_with_retry(provider, prompt, system)
    hook = str(parsed.get("hook", "")).strip()
    body = str(parsed.get("body", "")).strip()
    cta = str(parsed.get("cta", "")).strip()
    hashtags = [str(h).lstrip("#").strip().lower() for h in parsed.get("hashtags", []) if str(h).strip()]
    source_links = _source_links_for(candidate)

    text = _render_text(hook=hook, body=body, cta=cta, hashtags=hashtags, source_links=source_links)
    return GeneratedContent(
        channel="instagram",
        content_format="caption",
        text=text,
        hook=hook,
        body=body,
        cta=cta,
        hashtags=hashtags,
        source_links=source_links,
        character_count=len(text),
        generated_at=datetime.now(timezone.utc),
        model=provider.model,
        prompt_version=prompt_version,
    )


def _build_repo_prompt(candidate: Candidate, evaluation: Evaluation) -> str:
    gh = candidate.github
    full_name = gh.full_name if gh else candidate.display_name
    growth_pct = candidate.discovery.growth_percent if candidate.discovery else 0
    stars = candidate.discovery.star_delta if candidate.discovery else 0
    return (
        f"Repo: {full_name}\n"
        f"GitHub URL: https://github.com/{full_name}\n"
        f"Stars added in window: {stars}\n"
        f"Growth: +{growth_pct:.0f}%\n"
        f"Editorial summary: {evaluation.summary}\n"
        f"Why interesting: {evaluation.why_interesting}\n"
        f"Audience: {evaluation.audience}\n"
    )


def _build_hackathon_prompt(candidate: Candidate, evaluation: Evaluation) -> str:
    h = candidate.hackathon
    return (
        f"Project: {h.project_name if h else candidate.display_name}\n"
        f"Hackathon: {(h.hackathon_name if h else None) or 'unknown'}\n"
        f"Prize / award: {(h.prize if h else None) or 'none'}\n"
        f"Tech: {', '.join((h.technologies if h else []) or []) or 'unknown'}\n"
        f"Devpost: {h.devpost_url if h else ''}\n"
        f"GitHub: {(h.github_url if h else None) or '(missing)'}\n"
        f"Demo: {(h.demo_url if h else None) or '(missing)'}\n"
        f"Editorial summary: {evaluation.summary}\n"
        f"Why interesting: {evaluation.why_interesting}\n"
    )


def _source_links_for(candidate: Candidate) -> list[str]:
    if candidate.github:
        return [f"GitHub: https://github.com/{candidate.github.full_name}"]
    if candidate.hackathon:
        links = [f"Project: {candidate.hackathon.devpost_url}"]
        if candidate.hackathon.github_url:
            links.append(f"GitHub: {candidate.hackathon.github_url}")
        if candidate.hackathon.demo_url:
            links.append(f"Demo: {candidate.hackathon.demo_url}")
        return links
    return []


def _render_text(*, hook: str, body: str, cta: str, hashtags: list[str], source_links: list[str]) -> str:
    tag_line = " ".join(f"#{h.lstrip('#')}" for h in hashtags if h.strip())
    sections = [part for part in (hook, body, cta) if part]
    if tag_line:
        sections.append(tag_line)
    if source_links:
        sections.append("Links:\n" + "\n".join(source_links))
    return "\n\n".join(sections)[:CHAR_LIMIT]


def _call_with_retry(provider: LLMProvider, prompt: str, system: str) -> dict:
    raw = provider.generate(prompt, system=system)
    try:
        return _parse_json(raw)
    except (json.JSONDecodeError, ValueError):
        raw = provider.generate(prompt + "\n\nReturn ONLY valid JSON.", system=system)
        return _parse_json(raw)


def _parse_json(text: str) -> dict:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return json.loads(cleaned.strip())
