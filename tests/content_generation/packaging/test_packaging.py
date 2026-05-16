from datetime import datetime, timezone

from src.contracts.candidate import Candidate, CandidateSource, GithubSnapshot, HackathonSnapshot
from src.contracts.content import GeneratedContent
from src.contracts.media import MediaAsset
from src.content_generation.packaging import build_post_package
from src.content_generation.packaging.channels import (
    validate_instagram_package,
    validate_linkedin_package,
)


def _now():
    return datetime(2026, 5, 16, tzinfo=timezone.utc)


def _content(channel: str, **overrides) -> GeneratedContent:
    base = dict(
        channel=channel,
        content_format="caption" if channel == "instagram" else "commentary",
        text="x" * 1200,
        hook="hook",
        body="body",
        cta="cta",
        hashtags=["a", "b", "c", "d"],
        source_links=["https://github.com/example/x"],
        character_count=1200,
        generated_at=_now(),
        model="m",
        prompt_version="v",
    )
    base.update(overrides)
    return GeneratedContent(**base)


def _media(channel: str) -> MediaAsset:
    return MediaAsset(
        asset_id="asset_1",
        channel=channel,
        local_path="output/x.jpg",
        width=1024,
        height=1024 if channel == "instagram" else 1536,
        aspect_ratio="1:1" if channel == "instagram" else "2:3",
        alt_text="A poster",
        image_prompt_version="v",
        generated_at=_now(),
    )


def _gh_candidate() -> Candidate:
    gh = GithubSnapshot(
        owner="example", repo="x", full_name="example/x", url="https://github.com/example/x"
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
        github=gh,
    )


def test_instagram_validator_flags_short_hashtags():
    issues = validate_instagram_package(_content("instagram", hashtags=["a"]), [_media("instagram")])
    assert any("3 hashtags" in m for m in issues)


def test_linkedin_validator_flags_short_text():
    issues = validate_linkedin_package(_content("linkedin", text="x", character_count=1), [_media("linkedin")])
    assert any("short" in m for m in issues)


def test_build_package_emits_ready_for_review():
    pkg = build_post_package(
        _gh_candidate(), _content("instagram"), [_media("instagram")], run_id="run_1", channel="instagram"
    )
    assert pkg.status == "ready_for_review"
    assert pkg.channel == "instagram"
    assert pkg.media[0].asset_id == "asset_1"
    assert pkg.post_id.startswith("post_instagram_")
