from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.models import Caption, Evaluation, HackathonCandidate
from src.render.renderer import render_html, render_hackathon_carousel, render_repo_card


def _eval():
    return Evaluation(
        content_type="repo",
        repo_id=1,
        full_name="awesome-co/zerodb",
        summary="A 1ms KV store in pure Python.",
        why_interesting="Drop-in Redis replacement.",
        audience="Backend devs",
        novelty_score=8.5, explainability_score=9.0, overall_score=8.7,
        stars_48h=420, growth_pct=380.0,
    )


def _caption():
    return Caption(
        hook="A 1ms KV store, in pure Python.",
        body="No C deps. Drop-in for Redis.",
        cta="Star on GitHub.",
        hashtags=["python", "opensource"],
    )


def test_render_html_smoke():
    html = render_html(
        "repo_card.html",
        {
            "repo_full_name": "awesome-co/zerodb",
            "repo_short_name": "zerodb",
            "stars_added": 420,
            "window_hours": 72,
            "growth_pct": 380,
            "summary": "1ms reads",
            "tagline": "Drop-in Redis.",
            "language": "Python",
            "audience": "backend devs",
            "novelty": 8.5, "explainability": 9.0, "overall": 8.7,
        },
    )
    assert "zerodb" in html
    assert "+420" in html
    assert "+380%" in html
    assert "Python" in html


def test_render_repo_card_invokes_playwright(tmp_path):
    """We mock Playwright so the test runs offline / without browser binaries."""
    out_dir = tmp_path / "cards"

    fake_browser = MagicMock()
    fake_context = MagicMock()
    fake_page = MagicMock()
    fake_browser.new_context.return_value = fake_context
    fake_context.new_page.return_value = fake_page

    def fake_screenshot(path, **kwargs):
        Path(path).write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)
    fake_page.screenshot.side_effect = fake_screenshot

    fake_p = MagicMock()
    fake_p.chromium.launch.return_value = fake_browser

    fake_sync_pw = MagicMock()
    fake_sync_pw.__enter__ = MagicMock(return_value=fake_p)
    fake_sync_pw.__exit__ = MagicMock(return_value=False)

    with patch("playwright.sync_api.sync_playwright", return_value=fake_sync_pw):
        result = render_repo_card(_eval(), _caption(), out_dir, window_hours=72, language="Python")

    assert result.media_type == "single"
    assert len(result.paths) == 1
    fake_page.set_content.assert_called_once()
    # First arg is the rendered HTML
    html_arg = fake_page.set_content.call_args.args[0]
    assert "zerodb" in html_arg


def test_render_carousel_makes_four_slides(tmp_path):
    out_dir = tmp_path / "cards"
    candidate = HackathonCandidate(
        devpost_url="https://devpost.com/software/pixelchef",
        project_name="PixelChef",
        hackathon_name="HackMIT",
        prize="Best Overall",
        github_url="https://github.com/x/pixelchef",
        first_seen_at=datetime.now(timezone.utc),
        technologies=["python", "ffmpeg"],
    )

    fake_browser = MagicMock()
    fake_context = MagicMock()
    fake_page = MagicMock()
    fake_browser.new_context.return_value = fake_context
    fake_context.new_page.return_value = fake_page

    def fake_screenshot(path, **kwargs):
        Path(path).write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)
    fake_page.screenshot.side_effect = fake_screenshot

    fake_p = MagicMock()
    fake_p.chromium.launch.return_value = fake_browser

    fake_sync_pw = MagicMock()
    fake_sync_pw.__enter__ = MagicMock(return_value=fake_p)
    fake_sync_pw.__exit__ = MagicMock(return_value=False)

    with patch("playwright.sync_api.sync_playwright", return_value=fake_sync_pw):
        result = render_hackathon_carousel(_eval(), candidate, _caption(), out_dir)

    assert result.media_type == "carousel"
    assert len(result.paths) == 4
    assert fake_page.set_content.call_count == 4
