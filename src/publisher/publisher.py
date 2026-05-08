from __future__ import annotations

import json
import logging
import sqlite3

from src.models import Caption, Evaluation, RenderResult, SavedPost

_log = logging.getLogger(__name__)


def _create_post_row(
    db: sqlite3.Connection,
    run_id: str,
    evaluation_id: int,
    content_type: str,
    media_type: str,
    repo_id: int | None,
    hackathon_id: int | None,
    card_paths: list[str],
    caption_text: str,
) -> int:
    cur = db.execute(
        """
        INSERT INTO posts (
            evaluation_id, content_type, media_type, repo_id, hackathon_id,
            card_paths, caption, status, run_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'rendered', ?)
        """,
        (
            evaluation_id,
            content_type,
            media_type,
            repo_id,
            hackathon_id,
            json.dumps(card_paths),
            caption_text,
            run_id,
        ),
    )
    db.commit()
    return cur.lastrowid


def _find_existing_post(
    db: sqlite3.Connection,
    *,
    repo_id: int | None,
    hackathon_id: int | None,
) -> sqlite3.Row | None:
    if repo_id is not None:
        return db.execute(
            "SELECT id, status FROM posts WHERE repo_id = ?", (repo_id,)
        ).fetchone()
    if hackathon_id is not None:
        return db.execute(
            "SELECT id, status FROM posts WHERE hackathon_id = ?", (hackathon_id,)
        ).fetchone()
    return None


def _update_existing_post(
    db: sqlite3.Connection,
    post_id: int,
    *,
    run_id: str,
    evaluation_id: int,
    card_paths: list[str],
    caption_text: str,
) -> None:
    db.execute(
        """
        UPDATE posts SET
            status = 'rendered',
            evaluation_id = ?,
            run_id = ?,
            card_paths = ?,
            caption = ?,
            error_message = NULL
        WHERE id = ?
        """,
        (evaluation_id, run_id, json.dumps(card_paths), caption_text, post_id),
    )
    db.commit()


def save_post(
    *,
    db: sqlite3.Connection,
    run_id: str,
    evaluation: Evaluation,
    evaluation_id: int,
    render: RenderResult,
    caption: Caption,
    repo_id: int | None = None,
    hackathon_id: int | None = None,
) -> SavedPost:
    """Persist rendered post locally for human review. No upload, no publish."""
    caption_text = caption.render()

    existing = _find_existing_post(db, repo_id=repo_id, hackathon_id=hackathon_id)
    if existing:
        post_id = existing["id"]
        _update_existing_post(
            db, post_id,
            run_id=run_id, evaluation_id=evaluation_id,
            card_paths=render.paths, caption_text=caption_text,
        )
        _log.info("Updated post %d (re-rendered) for review", post_id)
    else:
        post_id = _create_post_row(
            db,
            run_id,
            evaluation_id,
            evaluation.content_type,
            render.media_type,
            repo_id,
            hackathon_id,
            render.paths,
            caption_text,
        )
        _log.info("Saved post %d for review: %s", post_id, render.paths[0])

    if repo_id is not None:
        db.execute("UPDATE repos_seen SET already_posted = 1 WHERE id = ?", (repo_id,))
    if hackathon_id is not None:
        db.execute("UPDATE hackathon_projects SET already_posted = 1 WHERE id = ?", (hackathon_id,))
    db.commit()

    return SavedPost(
        post_id=post_id,
        card_paths=list(render.paths),
        caption=caption_text,
    )
