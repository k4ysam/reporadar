from __future__ import annotations

import logging

import psycopg

from src.ai_gateway.llm.base import LLMProvider
from src.candidate_intelligence.evaluation.hackathon_evaluator import evaluate_hackathon
from src.candidate_intelligence.evaluation.repo_evaluator import evaluate_repo
from src.candidate_intelligence.repository import recent_evaluation_keys
from src.candidate_intelligence.source_adapters.github_discovery.client import GithubClient
from src.common.config import Settings
from src.contracts.candidate import Candidate
from src.contracts.evaluation import Evaluation

_log = logging.getLogger(__name__)


def evaluate_repo_candidates(
    candidates: list[Candidate],
    provider: LLMProvider,
    github_client: GithubClient,
    conn: psycopg.Connection,
    config: Settings,
) -> list[Evaluation]:
    recent = recent_evaluation_keys(conn, within_days=7)
    to_eval = [c for c in candidates if c.canonical_repo_key not in recent][
        : config.max_evaluations_per_run
    ]
    out: list[Evaluation] = []
    for candidate in to_eval:
        try:
            out.append(evaluate_repo(candidate, provider, github_client, conn))
        except Exception as exc:
            _log.error("Failed to evaluate repo %s: %s", candidate.canonical_repo_key, exc)
    out.sort(key=lambda e: e.scores.overall, reverse=True)
    return out


def evaluate_hackathon_candidates(
    candidates: list[Candidate],
    provider: LLMProvider,
    conn: psycopg.Connection,
    config: Settings,
) -> list[Evaluation]:
    recent = recent_evaluation_keys(conn, within_days=7)
    to_eval = [c for c in candidates if c.canonical_repo_key not in recent][
        : config.max_evaluations_per_run
    ]
    out: list[Evaluation] = []
    for candidate in to_eval:
        try:
            out.append(evaluate_hackathon(candidate, provider, conn))
        except Exception as exc:
            _log.error("Failed to evaluate hackathon %s: %s", candidate.canonical_repo_key, exc)
    out.sort(key=lambda e: e.scores.overall, reverse=True)
    return out
