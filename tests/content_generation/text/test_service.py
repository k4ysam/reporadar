from datetime import datetime, timezone

import pytest

from src.content_generation.text import generate_text
from src.contracts.candidate import (
    Candidate,
    CandidateSource,
    DiscoverySignals,
    GithubSnapshot,
    HackathonSnapshot,
)
from src.contracts.evaluation import Evaluation, EvaluationScores


class _StubProvider:
    name = "fake"
    model = "fake-model"

    def __init__(self, response):
        self._response = response
        self.calls = []

    def generate(self, prompt, system=None):
        self.calls.append((prompt, system))
        return self._response


def _now():
    return datetime(2026, 5, 16, tzinfo=timezone.utc)


def _evaluation():
    return Evaluation(
        evaluation_id="eval_1",
        candidate_id="cand_1",
        project_id="proj_1",
        run_id="run_1",
        evaluated_at=_now(),
        model="gpt-5",
        provider="openai",
        prompt_version="v",
        summary="A tool to do X",
        why_interesting="It saves time.",
        audience="developers",
        scores=EvaluationScores(novelty=8, explainability=9, overall=8.5),
    )


def _github_candidate():
    gh = GithubSnapshot(
        owner="example",
        repo="x",
        full_name="example/x",
        url="https://github.com/example/x",
        primary_language="Python",
        stars_count=1200,
        topics=["ai", "cli"],
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


def _hackathon_candidate():
    h = HackathonSnapshot(
        devpost_url="https://devpost.com/software/x",
        project_name="X",
        github_url="https://github.com/owner/x",
    )
    return Candidate(
        candidate_id="cand_h",
        project_id="proj_h",
        canonical_repo_key="devpost:x",
        run_id="run_1",
        source=CandidateSource(
            source_type="devpost_discovery",
            source_name="devpost_scrape",
            source_url=h.devpost_url,
            discovered_at=_now(),
        ),
        hackathon=h,
    )


def test_instagram_caption_for_repo():
    provider = _StubProvider(
        '{"hook": "h", "body": "b", "cta": "c", "hashtags": ["python", "ai"]}'
    )
    content = generate_text(_github_candidate(), _evaluation(), provider, channel="instagram")
    assert content.channel == "instagram"
    assert content.hook == "h"
    assert "python" in content.hashtags
    assert "github.com/example/x" in content.text


def test_linkedin_commentary_for_repo():
    provider = _StubProvider("This is a long LinkedIn post about example/x." * 30)
    content = generate_text(_github_candidate(), _evaluation(), provider, channel="linkedin")
    assert content.channel == "linkedin"
    assert content.content_format == "commentary"
    assert content.character_count > 0


def test_linkedin_rejects_hackathon():
    provider = _StubProvider("ignored")
    with pytest.raises(ValueError, match="only supports GitHub"):
        generate_text(_hackathon_candidate(), _evaluation(), provider, channel="linkedin")


def test_unknown_channel_raises():
    provider = _StubProvider("ignored")
    with pytest.raises(NotImplementedError):
        generate_text(_github_candidate(), _evaluation(), provider, channel="x")
