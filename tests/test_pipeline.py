from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from src import pipeline
from src.config import Settings
from src.models import Candidate, Caption, Evaluation, HackathonCandidate, RenderResult, SavedPost


def _repo_candidate() -> Candidate:
    now = datetime.now(timezone.utc)
    return Candidate(
        repo_id=101,
        full_name="owner/repo",
        stars_now=500,
        stars_48h_ago=100,
        growth_pct=400.0,
        created_at=now,
        first_seen_at=now,
    )


def _hackathon_candidate() -> HackathonCandidate:
    return HackathonCandidate(
        devpost_url="https://devpost.com/software/pixelchef",
        project_name="PixelChef",
        hackathon_name="HackNY",
        prize="Best Overall",
        github_url="https://github.com/x/y",
        first_seen_at=datetime.now(timezone.utc),
    )


def _repo_eval(overall_score: float) -> Evaluation:
    return Evaluation(
        content_type="repo",
        repo_id=1,
        full_name="owner/repo",
        summary="Repo summary.",
        why_interesting="Repo reason.",
        audience="Developers",
        novelty_score=8,
        explainability_score=8,
        overall_score=overall_score,
    )


def _hackathon_eval(overall_score: float) -> Evaluation:
    return Evaluation(
        content_type="hackathon",
        hackathon_id=1,
        full_name="PixelChef",
        summary="Hackathon summary.",
        why_interesting="Hackathon reason.",
        audience="Builders",
        novelty_score=9,
        explainability_score=9,
        overall_score=overall_score,
    )


def test_run_pipeline_picks_top_across_repos_and_hackathons(tmp_db, tmp_path, monkeypatch):
    tmp_db.execute(
        """
        INSERT INTO hackathon_projects (
            devpost_url, project_name, prize, github_url, first_seen_at, last_scan_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            "https://devpost.com/software/pixelchef",
            "PixelChef",
            "Best Overall",
            "https://github.com/x/y",
            "2026-05-01",
            "2026-05-01",
        ),
    )
    tmp_db.commit()

    repo_candidate = _repo_candidate()
    hackathon_candidate = _hackathon_candidate()
    repo_eval = _repo_eval(overall_score=6)
    hackathon_eval = _hackathon_eval(overall_score=9)
    provider = SimpleNamespace(name="openai")
    calls: list[str] = []
    saved_kwargs = {}

    def scan_repos(*_args, **_kwargs):
        calls.append("scan_repos")
        return [repo_candidate]

    def scan_devpost(*_args, **_kwargs):
        calls.append("scan_devpost")
        return [hackathon_candidate]

    def evaluate_repos(*_args, **_kwargs):
        calls.append("evaluate_repos")
        return [repo_eval]

    def evaluate_hackathons(*_args, **_kwargs):
        calls.append("evaluate_hackathons")
        return [hackathon_eval]

    def save_post(**kwargs):
        saved_kwargs.update(kwargs)
        return SavedPost(post_id=7, card_paths=["hackathon.jpg"], caption=kwargs["caption"].render())

    monkeypatch.setattr(pipeline, "get_provider", lambda *_args, **_kwargs: provider)
    monkeypatch.setattr(pipeline, "scan_repos", scan_repos)
    monkeypatch.setattr(pipeline, "scan_devpost", scan_devpost)
    monkeypatch.setattr(pipeline, "evaluate_candidates", evaluate_repos)
    monkeypatch.setattr(pipeline, "evaluate_hackathon_candidates", evaluate_hackathons)
    monkeypatch.setattr(pipeline, "_eval_id", lambda *_args, **_kwargs: 42)
    monkeypatch.setattr(
        pipeline,
        "generate_hackathon_caption",
        lambda *_args, **_kwargs: Caption(hook="Hook", body="Body", cta="CTA"),
    )
    monkeypatch.setattr(
        pipeline,
        "render_hackathon_card",
        lambda *_args, **_kwargs: RenderResult(media_type="carousel", paths=["hackathon.jpg"]),
    )
    monkeypatch.setattr(pipeline, "save_post", save_post)

    result = pipeline.run_pipeline(
        tmp_db,
        Settings(gh_token="tok", openai_api_key="sk-test", output_dir=str(tmp_path)),
    )

    assert result == SavedPost(post_id=7, card_paths=["hackathon.jpg"], caption="Hook\n\nBody\n\nCTA")
    assert calls == ["scan_repos", "scan_devpost", "evaluate_repos", "evaluate_hackathons"]
    assert saved_kwargs["evaluation"] == hackathon_eval
    assert saved_kwargs["hackathon_id"] == 1
    assert "repo_id" not in saved_kwargs
    run = tmp_db.execute("SELECT status FROM pipeline_runs").fetchone()
    assert run["status"] == "completed"


def test_run_pipeline_completes_without_post_when_all_sources_empty(tmp_db, tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "get_provider", lambda *_args, **_kwargs: SimpleNamespace(name="openai"))
    monkeypatch.setattr(pipeline, "scan_repos", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(pipeline, "scan_devpost", lambda *_args, **_kwargs: [])

    result = pipeline.run_pipeline(
        tmp_db,
        Settings(gh_token="tok", openai_api_key="sk-test", output_dir=str(tmp_path)),
    )

    assert result is None
    run = tmp_db.execute("SELECT status FROM pipeline_runs").fetchone()
    assert run["status"] == "completed"
