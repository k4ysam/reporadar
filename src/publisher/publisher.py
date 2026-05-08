from __future__ import annotations

import json
import logging
import sqlite3
import time
from datetime import datetime, timezone

from src.config import Settings
from src.models import Caption, Evaluation, PublishedPost, RenderResult
from src.publisher.image_host import ImageHost, get_image_host
from src.publisher.instagram import InstagramClient

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
    scheduled_for: datetime | None,
) -> int:
    cur = db.execute(
        """
        INSERT INTO posts (
            evaluation_id, content_type, media_type, repo_id, hackathon_id,
            card_paths, caption, status, scheduled_for, run_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'rendered', ?, ?)
        """,
        (
            evaluation_id,
            content_type,
            media_type,
            repo_id,
            hackathon_id,
            json.dumps(card_paths),
            caption_text,
            scheduled_for.isoformat() if scheduled_for else None,
            run_id,
        ),
    )
    db.commit()
    return cur.lastrowid


def _set_post_status(
    db: sqlite3.Connection,
    post_id: int,
    *,
    status: str,
    image_host_urls: list[str] | None = None,
    media_id: str | None = None,
    permalink: str | None = None,
    error: str | None = None,
    increment_retry: bool = False,
) -> None:
    fields = ["status = ?"]
    params: list = [status]
    if image_host_urls is not None:
        fields.append("image_host_urls = ?")
        params.append(json.dumps(image_host_urls))
    if media_id is not None:
        fields.append("instagram_media_id = ?")
        params.append(media_id)
    if permalink is not None:
        fields.append("instagram_permalink = ?")
        params.append(permalink)
    if status == "published":
        fields.append("published_at = ?")
        params.append(datetime.now(timezone.utc).isoformat())
    if error is not None:
        fields.append("error_message = ?")
        params.append(error[:500])
    if increment_retry:
        fields.append("retry_count = retry_count + 1")
    params.append(post_id)
    db.execute(f"UPDATE posts SET {', '.join(fields)} WHERE id = ?", params)
    db.commit()


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


def _reset_post_for_retry(
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
            error_message = NULL,
            image_host_urls = NULL
        WHERE id = ?
        """,
        (evaluation_id, run_id, json.dumps(card_paths), caption_text, post_id),
    )
    db.commit()


def publish_post(
    *,
    db: sqlite3.Connection,
    run_id: str,
    settings: Settings,
    evaluation: Evaluation,
    evaluation_id: int,
    render: RenderResult,
    caption: Caption,
    repo_id: int | None = None,
    hackathon_id: int | None = None,
    image_host: ImageHost | None = None,
    instagram: InstagramClient | None = None,
    max_retries: int = 3,
) -> PublishedPost | None:
    """Render → upload → publish, with cross-run idempotency and retry."""
    caption_text = caption.render()

    existing = _find_existing_post(db, repo_id=repo_id, hackathon_id=hackathon_id)
    if existing and existing["status"] == "published":
        _log.info(
            "Already published for repo_id=%s hackathon_id=%s (post id=%d) — skipping",
            repo_id, hackathon_id, existing["id"],
        )
        return None
    if existing:
        post_id = existing["id"]
        _reset_post_for_retry(
            db, post_id,
            run_id=run_id, evaluation_id=evaluation_id,
            card_paths=render.paths, caption_text=caption_text,
        )
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
            scheduled_for=None,
        )

    if settings.ig_dry_run:
        _log.info("IG_DRY_RUN=1 — skipping upload/publish for post %d", post_id)
        _set_post_status(db, post_id, status="rendered", error="dry-run")
        return None

    image_host = image_host or get_image_host(settings)
    instagram = instagram or InstagramClient(
        db, run_id, settings.ig_access_token, settings.ig_business_account_id
    )

    for attempt in range(1, max_retries + 1):
        try:
            urls = [image_host.upload(p) for p in render.paths]
            _set_post_status(db, post_id, status="uploaded", image_host_urls=urls)

            if render.media_type == "single":
                result = instagram.post_single(urls[0], caption_text)
            else:
                result = instagram.post_carousel(urls, caption_text)

            _set_post_status(
                db,
                post_id,
                status="published",
                media_id=result["media_id"],
                permalink=result.get("permalink"),
            )
            if repo_id is not None:
                db.execute("UPDATE repos_seen SET already_posted = 1 WHERE id = ?", (repo_id,))
            if hackathon_id is not None:
                db.execute("UPDATE hackathon_projects SET already_posted = 1 WHERE id = ?", (hackathon_id,))
            db.commit()

            return PublishedPost(
                post_id=post_id,
                instagram_media_id=result["media_id"],
                instagram_permalink=result.get("permalink") or "",
                published_at=datetime.now(timezone.utc),
            )
        except Exception as exc:
            _log.error("Publish attempt %d/%d failed: %s", attempt, max_retries, exc)
            _set_post_status(db, post_id, status="failed", error=str(exc), increment_retry=True)
            if attempt < max_retries:
                time.sleep(2 ** attempt)
    return None
