from datetime import datetime, timezone

from src.candidate_intelligence.evaluation.prompts import (
    HACKATHON_SYSTEM_PROMPT,
    REPO_SYSTEM_PROMPT,
    build_hackathon_prompt,
    build_repo_prompt,
)
from src.contracts.candidate import (
    Candidate,
    CandidateSource,
    DiscoverySignals,
    GithubSnapshot,
    HackathonSnapshot,
    RepoEnrichment,
)


def _source(stype, url):
    return CandidateSource(
        source_type=stype,
        source_name="test",
        source_url=url,
        discovered_at=datetime(2026, 5, 16, tzinfo=timezone.utc),
    )


def test_repo_prompt_includes_growth_and_readme():
    gh = GithubSnapshot(
        owner="example",
        repo="x",
        full_name="example/x",
        url="https://github.com/example/x",
        primary_language="Python",
        stars_count=1000,
        topics=["ai", "cli"],
    )
    candidate = Candidate(
        candidate_id="cand_1",
        project_id="proj_1",
        canonical_repo_key="github:example/x",
        run_id="run_1",
        source=_source("github_discovery", gh.url),
        discovery=DiscoverySignals(stars_at_discovery=1000, stars_window_ago=500, star_delta=500, growth_percent=100.0),
        github=gh,
    )
    enrichment = RepoEnrichment(readme="hello world readme", recent_commits=["feat: hi"])
    prompt = build_repo_prompt(candidate, enrichment)
    assert "example/x" in prompt
    assert "Python" in prompt
    assert "+100%" in prompt
    assert "hello world readme" in prompt
    assert "feat: hi" in prompt


def test_repo_system_prompt_includes_injection_guard():
    assert "ignore" in REPO_SYSTEM_PROMPT.lower()
    assert "evidence" in REPO_SYSTEM_PROMPT.lower()


def test_hackathon_prompt_uses_snapshot_fields():
    h = HackathonSnapshot(
        devpost_url="https://devpost.com/software/x",
        project_name="X",
        hackathon_name="HackOne",
        prize="Best Use of AI",
        github_url="https://github.com/owner/x",
        technologies=["python", "openai"],
    )
    cand = Candidate(
        candidate_id="cand_h",
        project_id="proj_h",
        canonical_repo_key="devpost:x",
        run_id="run_1",
        source=_source("devpost_discovery", h.devpost_url),
        hackathon=h,
    )
    prompt = build_hackathon_prompt(cand)
    assert "HackOne" in prompt
    assert "Best Use of AI" in prompt
    assert "python, openai" in prompt


def test_hackathon_system_prompt_blocks_injection():
    assert "ignore" in HACKATHON_SYSTEM_PROMPT.lower()
