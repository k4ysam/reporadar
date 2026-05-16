"""End-to-end Content Generation: text → media → packaging in one call."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from src.content_generation import generate_post_package
from src.contracts.candidate import (
    Candidate,
    CandidateSource,
    DiscoverySignals,
    GithubSnapshot,
)
from src.contracts.evaluation import Evaluation, EvaluationScores


def _now():
    return datetime(2026, 5, 16, tzinfo=timezone.utc)


def _candidate() -> Candidate:
    gh = GithubSnapshot(
        owner="example",
        repo="x",
        full_name="example/x",
        url="https://github.com/example/x",
        primary_language="Python",
        topics=["ai", "cli"],
        stars_count=1200,
    )
    return Candidate(
        candidate_id="cand_1",
        project_id="proj_1",
        canonical_repo_key="github:example/x",
        run_id="run_1",
        source=CandidateSource(
            source_type="github_discovery",
            source_name="github_search_api",
            source_url=gh.url,
            discovered_at=_now(),
        ),
        discovery=DiscoverySignals(stars_at_discovery=1200, star_delta=400, growth_percent=80),
        github=gh,
    )


def _evaluation() -> Evaluation:
    return Evaluation(
        evaluation_id="eval_1",
        candidate_id="cand_1",
        project_id="proj_1",
        run_id="run_1",
        evaluated_at=_now(),
        model="gpt-5",
        provider="openai",
        prompt_version="v",
        summary="A tool that does X",
        why_interesting="It is novel",
        audience="developers",
        scores=EvaluationScores(novelty=8, explainability=9, overall=8.5),
    )


class _StubLLMProvider:
    name = "openai"
    model = "gpt-5"

    def generate(self, prompt, system=None):
        return '{"hook": "Hook line", "body": "Body sentence.", "cta": "Try it.", "hashtags": ["ai", "cli", "python", "tools"]}'


class _StubSettings:
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        self.openai_api_key = "stub"


def test_generate_post_package_runs_all_three_stages(tmp_path: Path):
    settings = _StubSettings(str(tmp_path))

    with patch("src.content_generation.media.service.get_image_provider") as get_img:
        get_img.return_value.generate = lambda prompt, target: Path(target).write_bytes(b"\xff") or target

        package = generate_post_package(
            conn=None,
            settings=settings,
            run_id="run_1",
            candidate=_candidate(),
            evaluation=_evaluation(),
            provider=_StubLLMProvider(),
            channel="instagram",
        )

    assert package.channel == "instagram"
    assert package.status == "ready_for_review"
    assert package.content.hook == "Hook line"
    assert len(package.media) == 1
    assert package.media[0].channel == "instagram"
    assert Path(package.media[0].local_path).exists()
    assert package.post_id.startswith("post_instagram_")
