from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone

from src.config import Settings
from src.evaluator.fetcher import RepoContext, fetch_repo_context
from src.evaluator.prompts import (
    HACKATHON_SYSTEM_PROMPT,
    REPO_SYSTEM_PROMPT,
    blocks_to_text,
    build_hackathon_prompt,
    build_user_prompt_blocks,
)
from src.llm.provider import LLMProvider
from src.models import Candidate, Evaluation, HackathonCandidate


def _parse_evaluation_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text.strip())


def _call_with_retry(provider: LLMProvider, prompt: str, system: str) -> tuple[dict, str]:
    raw = provider.generate(prompt, system=system)
    try:
        return _parse_evaluation_json(raw), raw
    except (json.JSONDecodeError, ValueError):
        retry = f"{prompt}\n\nReturn ONLY valid JSON. No explanation, no markdown."
        raw = provider.generate(retry, system=system)
        return _parse_evaluation_json(raw), raw


def evaluate_candidate(
    candidate: Candidate,
    provider: LLMProvider,
    github_client,
    db: sqlite3.Connection,
    run_id: str,
    config: Settings,
) -> Evaluation:
    ctx: RepoContext = fetch_repo_context(candidate.full_name, github_client)
    blocks = build_user_prompt_blocks(candidate, ctx)
    prompt_text = blocks_to_text(blocks)

    parsed, raw = _call_with_retry(provider, prompt_text, REPO_SYSTEM_PROMPT)

    evaluation = Evaluation(
        content_type="repo",
        repo_id=candidate.repo_id,
        full_name=candidate.full_name,
        summary=parsed["summary"],
        why_interesting=parsed["why_interesting"],
        audience=parsed["audience"],
        novelty_score=float(parsed["novelty_score"]),
        explainability_score=float(parsed["explainability_score"]),
        overall_score=float(parsed["overall_score"]),
        skip=bool(parsed.get("skip", False)),
        stars_48h=candidate.stars_now - candidate.stars_48h_ago,
        growth_pct=candidate.growth_pct,
        llm_provider=provider.name,
    )

    db.execute(
        """
        INSERT INTO evaluations
            (content_type, repo_id, run_id, evaluated_at, summary, why_interesting, audience,
             novelty_score, explainability_score, overall_score, skip, growth_pct,
             raw_response, llm_provider, claude_raw_response)
        SELECT 'repo', id, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        FROM repos_seen WHERE full_name = ?
        """,
        (
            run_id,
            datetime.now(timezone.utc).isoformat(),
            evaluation.summary,
            evaluation.why_interesting,
            evaluation.audience,
            evaluation.novelty_score,
            evaluation.explainability_score,
            evaluation.overall_score,
            int(evaluation.skip),
            evaluation.growth_pct,
            raw,
            provider.name,
            raw,  # legacy claude_raw_response column
            candidate.full_name,
        ),
    )
    db.commit()
    return evaluation


def evaluate_hackathon(
    candidate: HackathonCandidate,
    provider: LLMProvider,
    db: sqlite3.Connection,
    run_id: str,
    config: Settings,
) -> Evaluation:
    prompt_text = build_hackathon_prompt(candidate)
    parsed, raw = _call_with_retry(provider, prompt_text, HACKATHON_SYSTEM_PROMPT)

    row = db.execute(
        "SELECT id FROM hackathon_projects WHERE devpost_url = ?",
        (candidate.devpost_url,),
    ).fetchone()
    hackathon_id = row["id"] if row else None

    evaluation = Evaluation(
        content_type="hackathon",
        hackathon_id=hackathon_id,
        full_name=candidate.project_name,
        summary=parsed["summary"],
        why_interesting=parsed["why_interesting"],
        audience=parsed["audience"],
        novelty_score=float(parsed["novelty_score"]),
        explainability_score=float(parsed["explainability_score"]),
        overall_score=float(parsed["overall_score"]),
        skip=bool(parsed.get("skip", False)),
        llm_provider=provider.name,
    )

    db.execute(
        """
        INSERT INTO evaluations
            (content_type, hackathon_id, run_id, evaluated_at, summary, why_interesting, audience,
             novelty_score, explainability_score, overall_score, skip, raw_response, llm_provider)
        VALUES ('hackathon', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            hackathon_id,
            run_id,
            datetime.now(timezone.utc).isoformat(),
            evaluation.summary,
            evaluation.why_interesting,
            evaluation.audience,
            evaluation.novelty_score,
            evaluation.explainability_score,
            evaluation.overall_score,
            int(evaluation.skip),
            raw,
            provider.name,
        ),
    )
    db.commit()
    return evaluation
