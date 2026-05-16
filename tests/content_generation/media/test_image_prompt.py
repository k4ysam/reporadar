from datetime import datetime, timezone

import pytest

from src.contracts.candidate import (
    Candidate,
    CandidateSource,
    DiscoverySignals,
    GithubSnapshot,
)
from src.contracts.content import GeneratedContent
from src.contracts.evaluation import Evaluation, EvaluationScores
from src.content_generation.media.channels import PROFILES, get_profile
from src.content_generation.media.channels.instagram import build_instagram_image_prompt
from src.content_generation.media.channels.linkedin import build_linkedin_image_prompt


def _now():
    return datetime(2026, 5, 16, tzinfo=timezone.utc)


def _content(channel: str, hook="Bold hook"):
    return GeneratedContent(
        channel=channel,
        content_format="caption" if channel == "instagram" else "commentary",
        text="full text",
        hook=hook,
        generated_at=_now(),
        model="m",
        prompt_version="v",
        character_count=200,
    )


def _candidate(language="Python"):
    gh = GithubSnapshot(
        owner="example",
        repo="x",
        full_name="example/x",
        url="https://github.com/example/x",
        primary_language=language,
        stars_count=1000,
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
        discovery=DiscoverySignals(stars_at_discovery=1000, star_delta=400, growth_percent=80),
        github=gh,
    )


def _eval():
    return Evaluation(
        evaluation_id="eval_1",
        candidate_id="cand_1",
        project_id="proj_1",
        run_id="run_1",
        evaluated_at=_now(),
        model="m",
        provider="openai",
        prompt_version="v",
        summary="An AI agent that learns",
        why_interesting="It learns fast",
        audience="developers",
        scores=EvaluationScores(novelty=8, explainability=9, overall=8.5),
    )


def test_profiles_include_instagram_and_linkedin():
    assert "instagram" in PROFILES
    assert "linkedin" in PROFILES
    assert get_profile("instagram").aspect_ratio == "1:1"
    assert get_profile("linkedin").aspect_ratio == "2:3"


def test_unknown_channel_raises():
    with pytest.raises(NotImplementedError):
        get_profile("tiktok")


def test_instagram_prompt_contains_headline_and_brand():
    prompt = build_instagram_image_prompt(_candidate(), _eval(), _content("instagram"))
    assert "REPORADAR" in prompt
    assert "example/x" in prompt
    assert "1:1" in prompt or "square" in prompt.lower()


def test_linkedin_prompt_uses_tall_aspect_and_stats():
    prompt = build_linkedin_image_prompt(_candidate(), _eval(), _content("linkedin", hook="X learns fast"))
    assert "2:3" in prompt
    assert "+400 STARS" in prompt or "STARS" in prompt
    assert "REPORADAR" in prompt


def test_linkedin_prompt_picks_language_motif():
    prompt = build_linkedin_image_prompt(_candidate(language="Rust"), _eval(), _content("linkedin"))
    assert "gear" in prompt.lower() or "crab" in prompt.lower()
