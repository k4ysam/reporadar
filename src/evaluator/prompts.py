from __future__ import annotations

from src.evaluator.fetcher import RepoContext
from src.models import Candidate

SYSTEM_PROMPT = """You are an editorial agent for RepoRadar, a newsletter that surfaces \
genuinely novel GitHub repos before they go mainstream. Your job is to evaluate a repo \
and return a structured JSON assessment.

Scoring rubric:
- novelty_score (1-10): Is this genuinely new, or a clone/tutorial/toy project?
- explainability_score (1-10): Can a developer understand the value in one Instagram caption?
- overall_score (1-10): Weighted composite. Penalize hard: toy projects, obvious forks, \
repos with no README, repos whose star spike looks like bot activity.

Return ONLY valid JSON matching this exact schema — no markdown, no explanation:
{"summary": "...", "why_interesting": "...", "audience": "...", \
"novelty_score": 8, "explainability_score": 9, "overall_score": 8.5}"""


def build_user_prompt_blocks(candidate: Candidate, ctx: RepoContext) -> list[dict]:
    blocks: list[dict] = []

    stats_text = (
        f"Repo: {candidate.full_name}\n"
        f"Description: {ctx.description or '(none)'}\n"
        f"Language: {ctx.language or 'unknown'}\n"
        f"Topics: {', '.join(ctx.topics) or 'none'}\n"
        f"Stars now: {candidate.stars_now}\n"
        f"Stars 48h ago (approx): {candidate.stars_48h_ago}\n"
        f"Growth: +{candidate.growth_pct:.0f}%\n"
    )
    blocks.append({"type": "text", "text": stats_text})

    if ctx.readme:
        readme_block: dict = {"type": "text", "text": f"README:\n{ctx.readme[:8000]}"}
        if len(ctx.readme) > 1500:
            readme_block["cache_control"] = {"type": "ephemeral"}
        blocks.append(readme_block)

    if ctx.recent_commits:
        commits_text = "Recent commits:\n" + "\n".join(f"- {c}" for c in ctx.recent_commits[:10])
        blocks.append({"type": "text", "text": commits_text})

    if ctx.top_issues:
        issues_text = "Top open issues:\n" + "\n".join(f"- {i}" for i in ctx.top_issues[:10])
        blocks.append({"type": "text", "text": issues_text})

    return blocks
