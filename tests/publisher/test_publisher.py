from __future__ import annotations

import json
from datetime import datetime, timezone

from src.models import Caption, Evaluation, RenderResult
from src.publisher.publisher import save_post


def _eval(content_type: str = "repo", **overrides):
    base = dict(
        content_type=content_type,
        repo_id=1 if content_type == "repo" else None,
        hackathon_id=1 if content_type == "hackathon" else None,
        full_name="owner/repo" if content_type == "repo" else "Project",
        summary="x", why_interesting="y", audience="z",
        novelty_score=8, explainability_score=8, overall_score=8,
        stars_48h=200, growth_pct=200,
    )
    base.update(overrides)
    return Evaluation(**base)


def _caption():
    return Caption(hook="hi", body="b", cta="c", hashtags=["python"])


def _seed_repo(tmp_db, mock_run_id):
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
           VALUES ('repo', 1, ?, ?, 'x', 'y', 'z', 8, 8, 8, 'openai')""",
        (mock_run_id, datetime.now(timezone.utc).isoformat()),
    )
    tmp_db.commit()
    return tmp_db.execute("SELECT id FROM evaluations").fetchone()[0]


def _seed_hackathon(tmp_db, mock_run_id):
    tmp_db.execute(
        "INSERT INTO pipeline_runs (run_id, started_at, status) VALUES (?, '2026-05-01', 'running')",
        (mock_run_id,),
    )
    tmp_db.execute(
        """INSERT INTO hackathon_projects
           (devpost_url, project_name, prize, github_url, first_seen_at, last_scan_at)
           VALUES ('https://devpost.com/x', 'Project', 'Best Overall', 'https://github.com/x/y', '2026-05-01', '2026-05-01')"""
    )
    tmp_db.execute(
        """INSERT INTO evaluations
           (content_type, hackathon_id, run_id, evaluated_at, summary, why_interesting, audience,
            novelty_score, explainability_score, overall_score, llm_provider)
           VALUES ('hackathon', 1, ?, ?, 'x', 'y', 'z', 8, 8, 8, 'openai')""",
        (mock_run_id, datetime.now(timezone.utc).isoformat()),
    )
    tmp_db.commit()
    return tmp_db.execute("SELECT id FROM evaluations").fetchone()[0]


def test_save_post_creates_rendered_row(tmp_db, tmp_path, mock_run_id):
    eval_id = _seed_repo(tmp_db, mock_run_id)
    img = tmp_path / "card.jpg"
    img.write_bytes(b"\xff\xd8\xff")

    saved = save_post(
        db=tmp_db, run_id=mock_run_id,
        evaluation=_eval(), evaluation_id=eval_id,
        render=RenderResult(media_type="single", paths=[str(img)]),
        caption=_caption(),
        repo_id=1,
    )

    assert saved.post_id > 0
    assert saved.card_paths == [str(img)]
    assert "hi" in saved.caption  # caption hook included

    row = tmp_db.execute(
        "SELECT status, card_paths, caption, evaluation_id FROM posts WHERE id = ?",
        (saved.post_id,),
    ).fetchone()
    assert row["status"] == "rendered"
    assert json.loads(row["card_paths"]) == [str(img)]
    assert row["evaluation_id"] == eval_id


def test_save_post_marks_repo_already_posted(tmp_db, tmp_path, mock_run_id):
    eval_id = _seed_repo(tmp_db, mock_run_id)
    img = tmp_path / "card.jpg"; img.write_bytes(b"\xff")

    save_post(
        db=tmp_db, run_id=mock_run_id,
        evaluation=_eval(), evaluation_id=eval_id,
        render=RenderResult(media_type="single", paths=[str(img)]),
        caption=_caption(),
        repo_id=1,
    )
    posted = tmp_db.execute("SELECT already_posted FROM repos_seen WHERE id = 1").fetchone()
    assert posted["already_posted"] == 1


def test_save_post_carousel(tmp_db, tmp_path, mock_run_id):
    eval_id = _seed_hackathon(tmp_db, mock_run_id)
    paths = []
    for i in range(4):
        p = tmp_path / f"slide_{i}.jpg"
        p.write_bytes(b"\xff")
        paths.append(str(p))

    saved = save_post(
        db=tmp_db, run_id=mock_run_id,
        evaluation=_eval(content_type="hackathon", repo_id=None, hackathon_id=1),
        evaluation_id=eval_id,
        render=RenderResult(media_type="carousel", paths=paths),
        caption=_caption(),
        hackathon_id=1,
    )

    assert len(saved.card_paths) == 4
    row = tmp_db.execute(
        "SELECT media_type, content_type FROM posts WHERE id = ?",
        (saved.post_id,),
    ).fetchone()
    assert row["media_type"] == "carousel"
    assert row["content_type"] == "hackathon"

    posted = tmp_db.execute("SELECT already_posted FROM hackathon_projects WHERE id = 1").fetchone()
    assert posted["already_posted"] == 1


def test_save_post_updates_existing_row(tmp_db, tmp_path, mock_run_id):
    """A second run for the same repo updates the existing post in place (UNIQUE on repo_id)."""
    eval_id = _seed_repo(tmp_db, mock_run_id)
    img1 = tmp_path / "v1.jpg"; img1.write_bytes(b"\xff")
    img2 = tmp_path / "v2.jpg"; img2.write_bytes(b"\xff")

    first = save_post(
        db=tmp_db, run_id=mock_run_id,
        evaluation=_eval(), evaluation_id=eval_id,
        render=RenderResult(media_type="single", paths=[str(img1)]),
        caption=_caption(),
        repo_id=1,
    )
    second = save_post(
        db=tmp_db, run_id=mock_run_id,
        evaluation=_eval(), evaluation_id=eval_id,
        render=RenderResult(media_type="single", paths=[str(img2)]),
        caption=_caption(),
        repo_id=1,
    )

    assert first.post_id == second.post_id
    rows = tmp_db.execute("SELECT id, card_paths FROM posts WHERE repo_id = 1").fetchall()
    assert len(rows) == 1
    assert json.loads(rows[0]["card_paths"]) == [str(img2)]
