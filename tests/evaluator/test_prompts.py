from datetime import datetime, timezone

from src.evaluator.fetcher import RepoContext
from src.evaluator.prompts import build_user_prompt_blocks
from src.models import Candidate


def _candidate():
    return Candidate(
        repo_id=1,
        full_name="owner/repo",
        stars_now=500,
        stars_48h_ago=100,
        growth_pct=400.0,
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        first_seen_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
    )


def _ctx(readme=None):
    return RepoContext(
        readme=readme,
        recent_commits=["fix: something", "feat: other thing"],
        top_issues=["Issue 1"],
        description="A test repo",
        topics=["python"],
        language="Python",
    )


def test_large_readme_gets_cache_control():
    ctx = _ctx(readme="x" * 2000)
    blocks = build_user_prompt_blocks(_candidate(), ctx)
    readme_blocks = [b for b in blocks if "README" in b.get("text", "")]
    assert any("cache_control" in b for b in readme_blocks)


def test_small_readme_no_cache_control():
    ctx = _ctx(readme="Short README.")
    blocks = build_user_prompt_blocks(_candidate(), ctx)
    readme_blocks = [b for b in blocks if "README" in b.get("text", "")]
    assert all("cache_control" not in b for b in readme_blocks)


def test_none_readme_excluded():
    ctx = _ctx(readme=None)
    blocks = build_user_prompt_blocks(_candidate(), ctx)
    assert not any("README" in b.get("text", "") for b in blocks)


def test_stats_block_contains_key_fields():
    ctx = _ctx(readme=None)
    blocks = build_user_prompt_blocks(_candidate(), ctx)
    stats = blocks[0]["text"]
    assert "owner/repo" in stats
    assert "400" in stats  # growth_pct
