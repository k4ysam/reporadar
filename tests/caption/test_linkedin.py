from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.caption.linkedin import generate_repo_linkedin_commentary
from src.models import Evaluation


def _eval() -> Evaluation:
    return Evaluation(
        content_type="repo",
        repo_id=1,
        full_name="awesome-co/zerodb",
        summary="A 1ms KV store in pure Python.",
        why_interesting="It can replace a Redis sidecar for small apps.",
        audience="Backend developers",
        novelty_score=8.5,
        explainability_score=9.0,
        overall_score=8.7,
        stars_48h=420,
        growth_pct=380.0,
    )


def test_generate_repo_linkedin_commentary_prompt_contains_required_context():
    provider = MagicMock()
    provider.generate.return_value = "zerodb is a small local KV store.\n\n#opensource #github"

    result = generate_repo_linkedin_commentary(
        _eval(),
        provider,
        repo_url="https://github.com/awesome-co/zerodb",
        language="Python",
        topics=["kv", "storage"],
    )

    assert result.startswith("zerodb is")
    prompt = provider.generate.call_args.args[0]
    system = provider.generate.call_args.kwargs["system"]
    assert "GitHub URL: https://github.com/awesome-co/zerodb" in prompt
    assert "Language: Python" in prompt
    assert "Topics: kv, storage" in prompt
    assert "Stars signal: 420 stars added" in prompt
    assert "Growth signal: +380%" in prompt
    assert "Editorial summary: A 1ms KV store" in prompt
    assert "Why interesting: It can replace" in prompt
    assert "900-1800 characters" in system
    assert "3-5 hashtags" in system
    assert "Do not invent benchmark numbers" in system


def test_generate_repo_linkedin_commentary_retries_empty_output():
    provider = MagicMock()
    provider.generate.side_effect = ["  \n", "Final LinkedIn post."]

    result = generate_repo_linkedin_commentary(
        _eval(),
        provider,
        repo_url="https://github.com/awesome-co/zerodb",
    )

    assert result == "Final LinkedIn post."
    assert provider.generate.call_count == 2


def test_generate_repo_linkedin_commentary_raises_after_empty_retry():
    provider = MagicMock()
    provider.generate.side_effect = ["", ""]

    with pytest.raises(ValueError, match="empty text"):
        generate_repo_linkedin_commentary(
            _eval(),
            provider,
            repo_url="https://github.com/awesome-co/zerodb",
        )
