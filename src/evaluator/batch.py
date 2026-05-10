from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timedelta, timezone

from src.config import Settings
from src.llm.provider import LLMProvider
from src.models import Candidate, Evaluation, HackathonCandidate

_log = logging.getLogger(__name__)


def evaluate_candidates(
    candidates: list[Candidate],
    provider: LLMProvider,
    github_client,
    db: sqlite3.Connection,
    run_id: str,
    config: Settings,
) -> list[Evaluation]:
    from src.evaluator.evaluator import evaluate_candidate

    allowed = config.max_evaluations_per_run

    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    recently_evaluated = {
        row[0]
        for row in db.execute(
            "SELECT DISTINCT repo_id FROM evaluations WHERE evaluated_at > ? AND repo_id IS NOT NULL",
            (cutoff,),
        ).fetchall()
    }

    to_evaluate = [c for c in candidates if c.repo_id not in recently_evaluated][:allowed]

    evaluations: list[Evaluation] = []
    for candidate in to_evaluate:
        try:
            ev = evaluate_candidate(candidate, provider, github_client, db, run_id, config)
            evaluations.append(ev)
        except Exception as exc:
            _log.error("Failed to evaluate %s: %s", candidate.full_name, exc)

    evaluations.sort(key=lambda e: e.overall_score, reverse=True)
    return evaluations


def evaluate_hackathon_candidates(
    candidates: list[HackathonCandidate],
    provider: LLMProvider,
    db: sqlite3.Connection,
    run_id: str,
    config: Settings,
) -> list[Evaluation]:
    from src.evaluator.evaluator import evaluate_hackathon

    allowed = config.max_evaluations_per_run

    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    recently = {
        row[0]
        for row in db.execute(
            "SELECT DISTINCT hackathon_id FROM evaluations WHERE evaluated_at > ? AND hackathon_id IS NOT NULL",
            (cutoff,),
        ).fetchall()
    }

    rows_by_url = {
        row["devpost_url"]: row["id"]
        for row in db.execute("SELECT id, devpost_url FROM hackathon_projects").fetchall()
    }
    to_evaluate = [
        c for c in candidates if rows_by_url.get(c.devpost_url) not in recently
    ][:allowed]

    evaluations: list[Evaluation] = []
    for candidate in to_evaluate:
        try:
            ev = evaluate_hackathon(candidate, provider, db, run_id, config)
            evaluations.append(ev)
        except Exception as exc:
            _log.error("Failed to evaluate hackathon %s: %s", candidate.project_name, exc)

    evaluations.sort(key=lambda e: e.overall_score, reverse=True)
    return evaluations
