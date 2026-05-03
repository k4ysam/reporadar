from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timedelta, timezone

from src.config import Settings
from src.models import Candidate, Evaluation

_log = logging.getLogger(__name__)


def _gemini_calls_today(db: sqlite3.Connection) -> int:
    row = db.execute(
        "SELECT COUNT(*) FROM api_calls WHERE service='gemini' AND called_at >= date('now')",
    ).fetchone()
    return row[0] if row else 0


def evaluate_candidates(
    candidates: list[Candidate],
    llm_client,
    github_client,
    db: sqlite3.Connection,
    run_id: str,
    config: Settings,
) -> list[Evaluation]:
    from src.evaluator.evaluator import evaluate_candidate

    calls_today = _gemini_calls_today(db)
    budget_remaining = config.gemini_daily_limit - calls_today
    if budget_remaining <= 0:
        _log.warning(
            "Gemini daily limit reached (%d/%d calls used today). Skipping evaluation.",
            calls_today, config.gemini_daily_limit,
        )
        return []

    allowed = min(config.max_evaluations_per_run, budget_remaining)
    if allowed < config.max_evaluations_per_run:
        _log.warning(
            "Only %d Gemini calls remaining today (limit %d, used %d). Capping this run at %d.",
            budget_remaining, config.gemini_daily_limit, calls_today, allowed,
        )

    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    recently_evaluated = {
        row[0]
        for row in db.execute(
            "SELECT DISTINCT e.repo_id FROM evaluations e "
            "JOIN repos_seen r ON r.id = e.repo_id "
            "WHERE e.evaluated_at > ?",
            (cutoff,),
        ).fetchall()
    }

    to_evaluate = [
        c for c in candidates if c.repo_id not in recently_evaluated
    ][:allowed]

    evaluations: list[Evaluation] = []
    for candidate in to_evaluate:
        try:
            ev = evaluate_candidate(candidate, llm_client, github_client, db, run_id, config)
            evaluations.append(ev)
        except Exception as exc:
            _log.error("Failed to evaluate %s: %s", candidate.full_name, exc)

    evaluations.sort(key=lambda e: e.overall_score, reverse=True)
    return evaluations
