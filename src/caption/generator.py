from __future__ import annotations

import json
import re

from src.llm.provider import LLMProvider
from src.models import Caption, Evaluation, HackathonCandidate

_REPO_SYSTEM = """You write short, punchy Instagram captions for RepoRadar, a dev-discovery account. \
Voice: confident, opinionated, never breathless. No corporate-speak, no emoji spam. One emoji max.

Constraints:
- hook: ≤80 chars, scroll-stopper. Opens with the *thing*, not a buildup.
- body: 2–4 short sentences (≤500 chars total). Concrete, specific, technical when warranted.
- cta: one short line, e.g. "Link in bio" or "★ on GitHub if it ships your stack".
- hashtags: 5–8 lowercase tags, no '#'. Mix broad (programming, opensource) + specific (lang, domain).

Return ONLY valid JSON: {"hook": "...", "body": "...", "cta": "...", "hashtags": ["..."]}"""

_HACKATHON_SYSTEM = """You write Instagram captions for RepoRadar's "Built in X hours" hackathon spotlight. \
Tone: punchy, builder-respecting, never condescending. One emoji max.

Constraints:
- hook: ≤80 chars. Lead with the *what* + the constraint ("Built a real-time mocap rig in 36 hours.").
- body: 2–4 sentences (≤500 chars). What it does, why it's impressive given the time.
- cta: short, e.g. "Builders linked below" or "Check the demo in bio".
- hashtags: 5–8 lowercase, no '#'. Include hackathon, devs, plus tech-stack tags.

Return ONLY valid JSON: {"hook": "...", "body": "...", "cta": "...", "hashtags": ["..."]}"""


def _parse_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text.strip())


def _to_caption(parsed: dict) -> Caption:
    return Caption(
        hook=str(parsed.get("hook", "")).strip(),
        body=str(parsed.get("body", "")).strip(),
        cta=str(parsed.get("cta", "")).strip(),
        hashtags=[str(h).lstrip("#").strip().lower() for h in parsed.get("hashtags", []) if str(h).strip()],
    )


def generate_repo_caption(evaluation: Evaluation, provider: LLMProvider) -> Caption:
    prompt = (
        f"Repo: {evaluation.full_name}\n"
        f"Stars added in window: {evaluation.stars_48h}\n"
        f"Growth: +{evaluation.growth_pct:.0f}%\n"
        f"Editorial summary: {evaluation.summary}\n"
        f"Why interesting: {evaluation.why_interesting}\n"
        f"Audience: {evaluation.audience}\n"
    )
    raw = provider.generate(prompt, system=_REPO_SYSTEM)
    try:
        parsed = _parse_json(raw)
    except (json.JSONDecodeError, ValueError):
        raw = provider.generate(prompt + "\n\nReturn ONLY valid JSON.", system=_REPO_SYSTEM)
        parsed = _parse_json(raw)
    return _to_caption(parsed)


def generate_hackathon_caption(
    evaluation: Evaluation,
    candidate: HackathonCandidate,
    provider: LLMProvider,
) -> Caption:
    prompt = (
        f"Project: {candidate.project_name}\n"
        f"Hackathon: {candidate.hackathon_name or 'unknown'}\n"
        f"Prize / award: {candidate.prize or 'none'}\n"
        f"Tech: {', '.join(candidate.technologies) or 'unknown'}\n"
        f"GitHub: {candidate.github_url or '(missing)'}\n"
        f"Editorial summary: {evaluation.summary}\n"
        f"Why interesting: {evaluation.why_interesting}\n"
    )
    raw = provider.generate(prompt, system=_HACKATHON_SYSTEM)
    try:
        parsed = _parse_json(raw)
    except (json.JSONDecodeError, ValueError):
        raw = provider.generate(prompt + "\n\nReturn ONLY valid JSON.", system=_HACKATHON_SYSTEM)
        parsed = _parse_json(raw)
    return _to_caption(parsed)
