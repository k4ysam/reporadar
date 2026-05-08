"""End-to-end pipeline runner.

Implements the PRD's content schedule:
- Monday    → repo post (single image)
- Wednesday → hackathon post (carousel)
- Friday    → repo post (single image)
"""
from __future__ import annotations

import logging
import sqlite3
import uuid
from datetime import datetime, timezone

from src.caption.generator import generate_hackathon_caption, generate_repo_caption
from src.config import Settings
from src.evaluator.batch import evaluate_candidates, evaluate_hackathon_candidates
from src.llm.provider import LLMProvider, get_provider
from src.models import Caption, Evaluation, HackathonCandidate, PublishedPost
from src.publisher.publisher import publish_post
from src.render.renderer import render_hackathon_carousel, render_repo_card
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


def run_repo_pipeline(
    db: sqlite3.Connection,
    settings: Settings,
) -> PublishedPost | None:
    run_id = _start_run(db)
    try:
        provider = get_provider(settings, db, run_id)

        candidates = scan_repos(db, settings, run_id)
        if not candidates:
            _log.info("No repo candidates this run.")
            _finish_run(db, run_id)
            return None

        gh_client = GithubClient(db, run_id, settings.gh_token)
        evaluations = evaluate_candidates(candidates, provider, gh_client, db, run_id, settings)
        top = _pick_top_eval(evaluations)
        if top is None:
            _log.info("No repo evaluation passed threshold.")
            _finish_run(db, run_id)
            return None

        # Find the matching candidate to grab language for the card
        match = next((c for c in candidates if c.full_name == top.full_name), None)
        caption = generate_repo_caption(top, provider)
        render = render_repo_card(
            top,
            caption,
            settings.output_dir,
            window_hours=settings.velocity_window_hours,
            language=match.language if match else None,
        )
        eval_id = _eval_id(db, top)
        if eval_id is None:
            raise RuntimeError("Could not resolve evaluation_id after insert")
        repo_row = db.execute(
            "SELECT id FROM repos_seen WHERE full_name = ?", (top.full_name,)
        ).fetchone()

        published = publish_post(
            db=db, run_id=run_id, settings=settings,
            evaluation=top, evaluation_id=eval_id,
            render=render, caption=caption,
            repo_id=repo_row["id"] if repo_row else None,
        )
        _finish_run(db, run_id)
        return published
    except Exception as exc:
        _finish_run(db, run_id, error=str(exc))
        raise


def run_hackathon_pipeline(
    db: sqlite3.Connection,
    settings: Settings,
) -> PublishedPost | None:
    run_id = _start_run(db)
    try:
        provider = get_provider(settings, db, run_id)

        candidates = scan_devpost(db, settings, run_id)
        if not candidates:
            _log.info("No hackathon candidates this run.")
            _finish_run(db, run_id)
            return None

        evaluations = evaluate_hackathon_candidates(candidates, provider, db, run_id, settings)
        top = _pick_top_eval(evaluations)
        if top is None:
            _log.info("No hackathon evaluation passed threshold.")
            _finish_run(db, run_id)
            return None

        match = _candidate_for_eval(candidates, db, top)
        if match is None:
            _log.warning("Could not match top eval back to candidate.")
            _finish_run(db, run_id)
            return None

        caption = generate_hackathon_caption(top, match, provider)
        render = render_hackathon_carousel(top, match, caption, settings.output_dir)

        eval_id = _eval_id(db, top)
        if eval_id is None:
            raise RuntimeError("Could not resolve evaluation_id after insert")

        published = publish_post(
            db=db, run_id=run_id, settings=settings,
            evaluation=top, evaluation_id=eval_id,
            render=render, caption=caption,
            hackathon_id=top.hackathon_id,
        )
        _finish_run(db, run_id)
        return published
    except Exception as exc:
        _finish_run(db, run_id, error=str(exc))
        raise


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


def run_for_today(db: sqlite3.Connection, settings: Settings, *, day_of_week: int | None = None) -> PublishedPost | None:
    """Dispatch based on weekday: 0=Mon ... 6=Sun. Mon/Fri repo, Wed hackathon."""
    if day_of_week is None:
        day_of_week = datetime.now(timezone.utc).weekday()
    if day_of_week in (0, 4):  # Monday, Friday
        return run_repo_pipeline(db, settings)
    if day_of_week == 2:  # Wednesday
        return run_hackathon_pipeline(db, settings)
    _log.info("No content scheduled for weekday %d.", day_of_week)
    return None
