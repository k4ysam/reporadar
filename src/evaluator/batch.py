from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from src.config import Settings
from src.models import Candidate, Evaluation


def evaluate_candidates(
    candidates: list[Candidate],
    anthropic_client,
    github_client,
    db: sqlite3.Connection,
    run_id: str,
    config: Settings,
) -> list[Evaluation]:
    from src.evaluator.evaluator import evaluate_candidate

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
    ][: config.max_evaluations_per_run]

    evaluations: list[Evaluation] = []
    for candidate in to_evaluate:
        try:
            ev = evaluate_candidate(candidate, anthropic_client, github_client, db, run_id, config)
            evaluations.append(ev)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).error("Failed to evaluate %s: %s", candidate.full_name, exc)

    evaluations.sort(key=lambda e: e.overall_score, reverse=True)
    return evaluations
