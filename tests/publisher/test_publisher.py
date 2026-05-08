from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from src.config import Settings
from src.models import Caption, Evaluation, RenderResult


def _eval():
    return Evaluation(
        content_type="repo",
        repo_id=1,
        full_name="owner/repo",
        summary="x", why_interesting="y", audience="z",
        novelty_score=8, explainability_score=8, overall_score=8,
        stars_48h=200, growth_pct=200,
    )


def _caption():
    return Caption(hook="hi", body="b", cta="c", hashtags=["python"])


def _seed(tmp_db, mock_run_id):
    tmp_db.execute(
        "INSERT INTO pipeline_runs (run_id, started_at, status) VALUES (?, '2026-05-01', 'running')",
        (mock_run_id,),
    )
    tmp_db.execute(
        "INSERT INTO repos_seen (full_name, first_seen_at, last_scan_at) VALUES (?, ?, ?)",
        ("owner/repo", "2026-05-01", "2026-05-01"),
    )
    tmp_db.execute(
        """INSERT INTO evaluations
           (content_type, repo_id, run_id, evaluated_at, summary, why_interesting, audience,
            novelty_score, explainability_score, overall_score, llm_provider)
           VALUES ('repo', 1, ?, ?, 'x', 'y', 'z', 8, 8, 8, 'gemini')""",
        (mock_run_id, datetime.now(timezone.utc).isoformat()),
    )
    tmp_db.commit()
    eval_id = tmp_db.execute("SELECT id FROM evaluations").fetchone()[0]
    return eval_id


def test_dry_run_skips_publish(tmp_db, tmp_path, mock_run_id):
    eval_id = _seed(tmp_db, mock_run_id)
    settings = Settings(gh_token="x", gemini_api_key="AIza", ig_dry_run=True, output_dir=str(tmp_path))

    from src.publisher.publisher import publish_post

    fake_render = RenderResult(media_type="single", paths=[str(tmp_path / "x.jpg")])
    result = publish_post(
        db=tmp_db, run_id=mock_run_id, settings=settings,
        evaluation=_eval(), evaluation_id=eval_id,
        render=fake_render, caption=_caption(),
        repo_id=1,
        image_host=MagicMock(), instagram=MagicMock(),
    )
    assert result is None
    row = tmp_db.execute("SELECT status FROM posts WHERE evaluation_id = ?", (eval_id,)).fetchone()
    assert row["status"] == "rendered"


def test_publish_happy_path(tmp_db, tmp_path, mock_run_id):
    eval_id = _seed(tmp_db, mock_run_id)
    settings = Settings(
        gh_token="x", gemini_api_key="AIza", ig_dry_run=False, output_dir=str(tmp_path),
        ig_access_token="t", ig_business_account_id="u",
    )

    img_path = tmp_path / "card.jpg"
    img_path.write_bytes(b"\xff\xd8\xff")

    fake_host = MagicMock()
    fake_host.upload.return_value = "https://cdn.example.com/card.jpg"
    fake_ig = MagicMock()
    fake_ig.post_single.return_value = {"media_id": "M1", "permalink": "https://insta/p/M1"}

    from src.publisher.publisher import publish_post
    fake_render = RenderResult(media_type="single", paths=[str(img_path)])
    result = publish_post(
        db=tmp_db, run_id=mock_run_id, settings=settings,
        evaluation=_eval(), evaluation_id=eval_id,
        render=fake_render, caption=_caption(),
        repo_id=1,
        image_host=fake_host, instagram=fake_ig,
    )

    assert result is not None
    assert result.instagram_media_id == "M1"
    row = tmp_db.execute("SELECT status, instagram_media_id FROM posts WHERE evaluation_id = ?", (eval_id,)).fetchone()
    assert row["status"] == "published"
    assert row["instagram_media_id"] == "M1"
    # repo flagged as already_posted
    posted = tmp_db.execute("SELECT already_posted FROM repos_seen WHERE id = 1").fetchone()
    assert posted["already_posted"] == 1


def test_idempotency_skips_already_published(tmp_db, tmp_path, mock_run_id):
    eval_id = _seed(tmp_db, mock_run_id)
    tmp_db.execute(
        """INSERT INTO posts (evaluation_id, content_type, media_type, repo_id, status, instagram_media_id)
           VALUES (NULL, 'repo', 'single', 1, 'published', 'M0')""",
    )
    tmp_db.commit()
    settings = Settings(
        gh_token="x", gemini_api_key="AIza", ig_dry_run=False, output_dir=str(tmp_path),
        ig_access_token="t", ig_business_account_id="u",
    )
    fake_host = MagicMock()
    fake_ig = MagicMock()
    img = tmp_path / "x.jpg"; img.write_bytes(b"\xff")

    from src.publisher.publisher import publish_post
    result = publish_post(
        db=tmp_db, run_id=mock_run_id, settings=settings,
        evaluation=_eval(), evaluation_id=eval_id,
        render=RenderResult(media_type="single", paths=[str(img)]),
        caption=_caption(), repo_id=1,
        image_host=fake_host, instagram=fake_ig,
    )
    assert result is None
    fake_ig.post_single.assert_not_called()
    fake_host.upload.assert_not_called()
    # Original published row is untouched
    row = tmp_db.execute("SELECT instagram_media_id, status FROM posts WHERE repo_id = 1").fetchone()
    assert row["status"] == "published"
    assert row["instagram_media_id"] == "M0"


def test_failed_post_is_retried_on_next_run(tmp_db, tmp_path, mock_run_id):
    """A prior failed post for the same repo gets reused, not blocked by UNIQUE."""
    eval_id = _seed(tmp_db, mock_run_id)
    tmp_db.execute(
        """INSERT INTO posts (evaluation_id, content_type, media_type, repo_id, status, error_message, retry_count)
           VALUES (NULL, 'repo', 'single', 1, 'failed', 'old error', 3)""",
    )
    tmp_db.commit()
    old_post_id = tmp_db.execute("SELECT id FROM posts WHERE repo_id = 1").fetchone()[0]

    settings = Settings(
        gh_token="x", gemini_api_key="AIza", ig_dry_run=False, output_dir=str(tmp_path),
        ig_access_token="t", ig_business_account_id="u",
    )
    img = tmp_path / "card.jpg"; img.write_bytes(b"\xff\xd8\xff")
    fake_host = MagicMock()
    fake_host.upload.return_value = "https://cdn.example.com/card.jpg"
    fake_ig = MagicMock()
    fake_ig.post_single.return_value = {"media_id": "M-new", "permalink": "https://insta/p/M-new"}

    from src.publisher.publisher import publish_post
    result = publish_post(
        db=tmp_db, run_id=mock_run_id, settings=settings,
        evaluation=_eval(), evaluation_id=eval_id,
        render=RenderResult(media_type="single", paths=[str(img)]),
        caption=_caption(), repo_id=1,
        image_host=fake_host, instagram=fake_ig,
    )
    assert result is not None
    assert result.instagram_media_id == "M-new"
    # Same row reused (no IntegrityError, no new row)
    rows = tmp_db.execute("SELECT id, status, error_message FROM posts WHERE repo_id = 1").fetchall()
    assert len(rows) == 1
    assert rows[0]["id"] == old_post_id
    assert rows[0]["status"] == "published"
    assert rows[0]["error_message"] is None
