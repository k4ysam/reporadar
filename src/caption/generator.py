from __future__ import annotations

import json
import re

from src.llm.provider import LLMProvider
from src.models import Caption, Evaluation, HackathonCandidate

_REPO_SYSTEM = """You write short, punchy Instagram captions for RepoRadar, a dev-discovery account. \
Voice: confident, opinionated, never breathless. No corporate-speak, no emoji spam. One emoji max.

Constraints:
- hook: ≤80 chars, one catchy summary line that appears before the rest of the description. Opens with the *thing*, not a buildup.
- body: 2–4 short sentences (≤500 chars total). Concrete, specific, technical when warranted. Do not repeat the hook.
- cta: one short line, e.g. "Worth starring if it fits your stack." or "Follow RepoRadar for more builder finds."
- hashtags: 5–8 lowercase tags, no '#'. Mix broad (programming, opensource) + specific (lang, domain).
- Do not include URLs in hook, body, cta, or hashtags; source links are appended separately.

Return ONLY valid JSON: {"hook": "...", "body": "...", "cta": "...", "hashtags": ["..."]}"""

_HACKATHON_SYSTEM = """You write Instagram captions for RepoRadar's "Built in X hours" hackathon spotlight. \
Tone: punchy, builder-respecting, never condescending. One emoji max.

Constraints:
- hook: ≤80 chars, one catchy summary line that appears before the rest of the description. Lead with the *what* + the constraint ("Built a real-time mocap rig in 36 hours.").
- body: 2–4 sentences (≤500 chars). What it does, why it's impressive given the time. Do not repeat the hook.
- cta: short, e.g. "Builders linked below." or "Demo and repo below."
- hashtags: 5–8 lowercase, no '#'. Include hackathon, devs, plus tech-stack tags.
- Do not include URLs in hook, body, cta, or hashtags; source links are appended separately.

Return ONLY valid JSON: {"hook": "...", "body": "...", "cta": "...", "hashtags": ["..."]}"""


def _parse_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text.strip())


def _dedupe_links(links: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for link in links:
        cleaned = link.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        deduped.append(cleaned)
    return deduped


def _to_caption(parsed: dict, *, source_links: list[str] | None = None) -> Caption:
    return Caption(
        hook=str(parsed.get("hook", "")).strip(),
        body=str(parsed.get("body", "")).strip(),
        cta=str(parsed.get("cta", "")).strip(),
        hashtags=[str(h).lstrip("#").strip().lower() for h in parsed.get("hashtags", []) if str(h).strip()],
        source_links=_dedupe_links(source_links or []),
    )


def generate_repo_caption(
    evaluation: Evaluation,
    provider: LLMProvider,
    *,
    repo_url: str | None = None,
) -> Caption:
    resolved_repo_url = repo_url or f"https://github.com/{evaluation.full_name}"
    prompt = (
        f"Repo: {evaluation.full_name}\n"
        f"GitHub URL: {resolved_repo_url}\n"
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
    return _to_caption(parsed, source_links=[f"GitHub: {resolved_repo_url}"])


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
        f"Devpost: {candidate.devpost_url}\n"
        f"GitHub: {candidate.github_url or '(missing)'}\n"
        f"Demo: {candidate.demo_url or '(missing)'}\n"
        f"Editorial summary: {evaluation.summary}\n"
        f"Why interesting: {evaluation.why_interesting}\n"
    )
    raw = provider.generate(prompt, system=_HACKATHON_SYSTEM)
    try:
        parsed = _parse_json(raw)
    except (json.JSONDecodeError, ValueError):
        raw = provider.generate(prompt + "\n\nReturn ONLY valid JSON.", system=_HACKATHON_SYSTEM)
        parsed = _parse_json(raw)
    source_links = [
        f"Project: {candidate.devpost_url}",
        f"GitHub: {candidate.github_url}" if candidate.github_url else "",
        f"Demo: {candidate.demo_url}" if candidate.demo_url else "",
    ]
    return _to_caption(parsed, source_links=source_links)
