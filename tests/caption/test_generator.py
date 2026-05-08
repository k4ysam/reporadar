from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from src.caption.generator import generate_hackathon_caption, generate_repo_caption
from src.models import Caption, Evaluation, HackathonCandidate


def _eval(content_type="repo"):
    return Evaluation(
        content_type=content_type,
        repo_id=1 if content_type == "repo" else None,
        hackathon_id=1 if content_type == "hackathon" else None,
        full_name="owner/repo" if content_type == "repo" else "PixelChef",
        summary="A blazing-fast KV store.",
        why_interesting="Sub-1ms reads.",
        audience="Backend devs",
        novelty_score=8.5, explainability_score=9.0, overall_score=8.5,
        stars_48h=400, growth_pct=400.0,
    )


GOOD_CAPTION_JSON = json.dumps({
    "hook": "A 1ms KV store, in pure Python.",
    "body": "Drop-in for Redis, no C deps. Authors claim p99 < 1ms.",
    "cta": "Link in bio.",
    "hashtags": ["python", "opensource", "redis", "database", "performance"],
})


def _provider(text):
    p = MagicMock()
    p.name = "gemini"
    p.generate.return_value = text
    return p


def test_generate_repo_caption_returns_caption():
    cap = generate_repo_caption(_eval(), _provider(GOOD_CAPTION_JSON))
    assert isinstance(cap, Caption)
    assert cap.hook.startswith("A 1ms")
    assert "python" in cap.hashtags


def test_caption_render_under_2200_chars():
    cap = generate_repo_caption(_eval(), _provider(GOOD_CAPTION_JSON))
    assert len(cap.render()) <= 2200
    rendered = cap.render()
    assert cap.hook in rendered
    assert "#python" in rendered


def test_strips_hash_prefix_in_hashtags():
    payload = json.dumps({
        "hook": "h", "body": "b", "cta": "c",
        "hashtags": ["#python", "##rust", "go"],
    })
    cap = generate_repo_caption(_eval(), _provider(payload))
    assert cap.hashtags == ["python", "rust", "go"]


def test_retry_on_bad_json():
    provider = MagicMock()
    provider.name = "gemini"
    provider.generate.side_effect = ["not json", GOOD_CAPTION_JSON]
    cap = generate_repo_caption(_eval(), provider)
    assert provider.generate.call_count == 2
    assert "Python" in cap.hook


def test_generate_hackathon_caption():
    candidate = HackathonCandidate(
        devpost_url="https://devpost.com/software/x",
        project_name="PixelChef",
        prize="Best Overall",
        github_url="https://github.com/x/y",
        first_seen_at=datetime.now(timezone.utc),
        technologies=["python", "ffmpeg"],
    )
    cap = generate_hackathon_caption(_eval("hackathon"), candidate, _provider(GOOD_CAPTION_JSON))
    assert cap.hook
