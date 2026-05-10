"""End-to-end pipeline runner.

Each run discovers repos and hackathon projects, evaluates both pools, renders
the top candidate across all content types, and saves it locally for human
review. No automatic upload or publishing.
"""
from __future__ import annotations

import logging
import sqlite3
import uuid
from datetime import datetime, timezone

from src.caption.generator import generate_hackathon_caption, generate_repo_caption
from src.config import Settings
from src.evaluator.batch import evaluate_candidates, evaluate_hackathon_candidates
from src.llm.provider import get_provider
from src.models import Evaluation, HackathonCandidate, SavedPost
from src.publisher.publisher import save_post
from src.render.image_gen import OpenAIImageClient
from src.render.renderer import render_hackathon_card, render_repo_card
from src.sources.devpost.scanner import scan_devpost
from src.sources.github_repos.client import GithubClient
from src.sources.github_repos.scanner import scan as scan_repos

_log = logging.getLogger(__name__)


def _start_run(db: sqlite3.Connection) -> str:
    run_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO pipeline_runs (run_id, started_at, status) VALUES (?, ?, 'running')",
        (run_id, datetime.now(timezone.utc).isoformat()),
    )
    db.commit()
    return run_id


def _finish_run(db: sqlite3.Connection, run_id: str, error: str | None = None) -> None:
    if error is None:
        db.execute(
            "UPDATE pipeline_runs SET status='completed', completed_at=? WHERE run_id=?",
            (datetime.now(timezone.utc).isoformat(), run_id),
        )
    else:
        db.execute(
            "UPDATE pipeline_runs SET status='failed', completed_at=?, error_message=? WHERE run_id=?",
            (datetime.now(timezone.utc).isoformat(), error[:500], run_id),
        )
    db.commit()


def _pick_top_eval(evaluations: list[Evaluation]) -> Evaluation | None:
    eligible = [e for e in evaluations if not e.skip]
    if not eligible:
        return None
    return max(eligible, key=lambda e: e.overall_score)


def _eval_id(db: sqlite3.Connection, evaluation: Evaluation) -> int | None:
    if evaluation.content_type == "repo":
        row = db.execute(
            """
            SELECT e.id FROM evaluations e
            JOIN repos_seen r ON r.id = e.repo_id
            WHERE r.full_name = ?
            ORDER BY e.id DESC LIMIT 1
            """,
            (evaluation.full_name,),
        ).fetchone()
    else:
        row = db.execute(
            "SELECT id FROM evaluations WHERE hackathon_id = ? ORDER BY id DESC LIMIT 1",
            (evaluation.hackathon_id,),
        ).fetchone()
    return row["id"] if row else None


def _render_repo_post(
    db: sqlite3.Connection,
    settings: Settings,
    run_id: str,
    provider,
    evaluation: Evaluation,
    candidates: list,
) -> SavedPost | None:
    match = next((c for c in candidates if c.full_name == evaluation.full_name), None)
    repo_url = f"https://github.com/{evaluation.full_name}"
    caption = generate_repo_caption(evaluation, provider, repo_url=repo_url)
    image_client = OpenAIImageClient(db, run_id, settings.openai_api_key)
    render = render_repo_card(
        evaluation,
        caption,
        settings.output_dir,
        image_client,
        window_hours=settings.velocity_window_hours,
        language=match.language if match else None,
    )
    eval_id = _eval_id(db, evaluation)
    if eval_id is None:
        raise RuntimeError("Could not resolve evaluation_id after insert")
    repo_row = db.execute(
        "SELECT id FROM repos_seen WHERE full_name = ?", (evaluation.full_name,)
    ).fetchone()

    return save_post(
        db=db, run_id=run_id,
        evaluation=evaluation, evaluation_id=eval_id,
        render=render, caption=caption,
        repo_id=repo_row["id"] if repo_row else None,
    )


def _render_hackathon_post(
    db: sqlite3.Connection,
    settings: Settings,
    run_id: str,
    provider,
    evaluation: Evaluation,
    candidates: list[HackathonCandidate],
) -> SavedPost | None:
    match = _candidate_for_eval(candidates, db, evaluation)
    if match is None:
        _log.warning("Could not match top eval back to candidate.")
        return None

    caption = generate_hackathon_caption(evaluation, match, provider)
    image_client = OpenAIImageClient(db, run_id, settings.openai_api_key)
    render = render_hackathon_card(evaluation, match, caption, settings.output_dir, image_client)

    eval_id = _eval_id(db, evaluation)
    if eval_id is None:
        raise RuntimeError("Could not resolve evaluation_id after insert")

    return save_post(
        db=db, run_id=run_id,
        evaluation=evaluation, evaluation_id=eval_id,
        render=render, caption=caption,
        hackathon_id=evaluation.hackathon_id,
    )


def _candidate_for_eval(
    candidates: list[HackathonCandidate],
    db: sqlite3.Connection,
    evaluation: Evaluation,
) -> HackathonCandidate | None:
    if evaluation.hackathon_id is None:
        return None
    row = db.execute(
        "SELECT devpost_url FROM hackathon_projects WHERE id = ?",
        (evaluation.hackathon_id,),
    ).fetchone()
    if not row:
        return None
    return next((c for c in candidates if c.devpost_url == row["devpost_url"]), None)


def run_pipeline(db: sqlite3.Connection, settings: Settings) -> SavedPost | None:
    """Run discovery, evaluation, and rendering across all content types."""
    run_id = _start_run(db)
    try:
        provider = get_provider(settings, db, run_id)

        repo_candidates = scan_repos(db, settings, run_id)
        hackathon_candidates = scan_devpost(db, settings, run_id)
        if not repo_candidates and not hackathon_candidates:
            _log.info("No candidates from any source this run.")
            _finish_run(db, run_id)
            return None

        gh_client = GithubClient(db, run_id, settings.gh_token)
        repo_evaluations = evaluate_candidates(
            repo_candidates, provider, gh_client, db, run_id, settings
        )
        hackathon_evaluations = evaluate_hackathon_candidates(
            hackathon_candidates, provider, db, run_id, settings
        )

        top = _pick_top_eval(repo_evaluations + hackathon_evaluations)
        if top is None:
            _log.info("No evaluation passed threshold across any content type.")
            _finish_run(db, run_id)
            return None

        if top.content_type == "hackathon":
            saved = _render_hackathon_post(
                db, settings, run_id, provider, top, hackathon_candidates
            )
        else:
            saved = _render_repo_post(
                db, settings, run_id, provider, top, repo_candidates
            )

        _finish_run(db, run_id)
        return saved
    except Exception as exc:
        _finish_run(db, run_id, error=str(exc))
        raise
