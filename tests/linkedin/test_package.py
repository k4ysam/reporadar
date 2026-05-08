from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.linkedin.package import (
    build_repo_alt_text,
    build_repo_linkedin_package,
    build_repo_poster_headline,
)
from src.models import Evaluation, RenderResult


def _eval(**overrides) -> Evaluation:
    base = dict(
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
    base.update(overrides)
    return Evaluation(**base)


def test_build_repo_poster_headline_is_short_and_repo_specific():
    headline = build_repo_poster_headline(
        _eval(summary="Turns local files into a queryable agent memory layer.")
    )

    assert headline.startswith("zerodb:")
    assert "agent memory" in headline
    assert len(headline) <= 92


def test_build_repo_alt_text_includes_repo_headline_and_metrics():
    headline = "zerodb: A 1ms KV store in pure Python"

    alt_text = build_repo_alt_text(_eval(), headline)

    assert "awesome-co/zerodb" in alt_text
    assert headline in alt_text
    assert "420 stars added" in alt_text
    assert "380 percent growth" in alt_text


def test_build_repo_linkedin_package_returns_reviewable_payload(tmp_path):
    provider = MagicMock()
    provider.generate.return_value = "zerodb is getting attention from backend developers."
    render_result = RenderResult(media_type="single", paths=[str(tmp_path / "poster.jpg")])

    with patch("src.linkedin.package.render_linkedin_repo_poster", return_value=render_result) as render:
        package = build_repo_linkedin_package(
            _eval(),
            provider,
            tmp_path,
            language="Python",
            topics=["kv", "storage"],
            window_hours=72,
        )

    assert package.commentary == "zerodb is getting attention from backend developers."
    assert package.image_paths == [str(tmp_path / "poster.jpg")]
    assert package.repo_url == "https://github.com/awesome-co/zerodb"
    assert package.source_name == "awesome-co/zerodb"
    assert "RepoRadar poster" in package.alt_text
    render.assert_called_once()
    assert render.call_args.kwargs["language"] == "Python"
    assert render.call_args.kwargs["topics"] == ["kv", "storage"]
