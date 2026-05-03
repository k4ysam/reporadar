from __future__ import annotations

import json
import re
import sqlite3
import time
from datetime import datetime, timezone

from src.config import Settings
from src.db import log_api_call
from src.evaluator.fetcher import RepoContext, fetch_repo_context
from src.evaluator.prompts import SYSTEM_PROMPT, build_user_prompt_blocks
from src.models import Candidate, Evaluation


def _parse_evaluation_json(text: str) -> dict:
    text = text.strip()
    # Strip markdown code fences
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text.strip())


def evaluate_candidate(
    candidate: Candidate,
    anthropic_client,
    github_client,
    db: sqlite3.Connection,
    run_id: str,
    config: Settings,
) -> Evaluation:
    ctx: RepoContext = fetch_repo_context(candidate.full_name, github_client)
    blocks = build_user_prompt_blocks(candidate, ctx)

    def _call_claude(extra_instruction: str = "") -> str:
        messages = [{"role": "user", "content": blocks}]
        if extra_instruction:
            messages.append({"role": "user", "content": extra_instruction})
        t0 = time.monotonic()
        resp = anthropic_client.messages.create(
            model=config.anthropic_model,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=messages,
        )
        latency_ms = int((time.monotonic() - t0) * 1000)
        # SDK raises on non-2xx, so reaching here always means success
        log_api_call(db, run_id, "anthropic", "messages", 200, latency_ms)
        return resp.content[0].text

    raw = _call_claude()
    try:
        parsed = _parse_evaluation_json(raw)
    except (json.JSONDecodeError, ValueError):
        raw = _call_claude("Return ONLY valid JSON. No explanation, no markdown.")
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
             novelty_score, explainability_score, overall_score, claude_raw_response)
        SELECT id, ?, ?, ?, ?, ?, ?, ?, ?, ?
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
            raw,
            candidate.full_name,
        ),
    )
    db.commit()
    return evaluation
