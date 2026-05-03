from __future__ import annotations

import json
import re
import sqlite3
import time
from datetime import datetime, timezone

from src.config import Settings
from src.db import log_api_call
from src.evaluator.fetcher import RepoContext, fetch_repo_context
from src.evaluator.prompts import blocks_to_text, build_user_prompt_blocks
from src.models import Candidate, Evaluation


def _parse_evaluation_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text.strip())


def evaluate_candidate(
    candidate: Candidate,
    llm_client,
    github_client,
    db: sqlite3.Connection,
    run_id: str,
    config: Settings,
) -> Evaluation:
    ctx: RepoContext = fetch_repo_context(candidate.full_name, github_client)
    blocks = build_user_prompt_blocks(candidate, ctx)
    prompt_text = blocks_to_text(blocks)

    def _call_llm(extra_instruction: str = "") -> str:
        full_prompt = prompt_text if not extra_instruction else f"{prompt_text}\n\n{extra_instruction}"
        t0 = time.monotonic()
        resp = llm_client.generate_content(full_prompt)
        latency_ms = int((time.monotonic() - t0) * 1000)
        log_api_call(db, run_id, "gemini", "generate_content", 200, latency_ms)
        return resp.text

    raw = _call_llm()
    try:
        parsed = _parse_evaluation_json(raw)
    except (json.JSONDecodeError, ValueError):
        raw = _call_llm("Return ONLY valid JSON. No explanation, no markdown.")
        parsed = _parse_evaluation_json(raw)

    evaluation = Evaluation(
        repo_id=candidate.repo_id,
        full_name=candidate.full_name,
        summary=parsed["summary"],
        why_interesting=parsed["why_interesting"],
        audience=parsed["audience"],
        novelty_score=float(parsed["novelty_score"]),
        explainability_score=float(parsed["explainability_score"]),
        overall_score=float(parsed["overall_score"]),
        stars_48h=candidate.stars_now - candidate.stars_48h_ago,
        growth_pct=candidate.growth_pct,
    )

    db.execute(
        """
        INSERT INTO evaluations
            (repo_id, run_id, evaluated_at, summary, why_interesting, audience,
             novelty_score, explainability_score, overall_score, growth_pct, claude_raw_response)
        SELECT id, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
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
            evaluation.growth_pct,
            raw,
            candidate.full_name,
        ),
    )
    db.commit()
    return evaluation
