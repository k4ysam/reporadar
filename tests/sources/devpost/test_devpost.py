from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.sources.devpost.client import _parse_project_page, _parse_software_listing


def _seed_run(db, run_id):
    db.execute(
        "INSERT INTO pipeline_runs (run_id, started_at, status) VALUES (?, '2026-05-01', 'running')",
        (run_id,),
    )
    db.commit()


def test_parse_software_listing():
    html = """
    <html><body>
      <a class="block-wrapper-link" href="/software/pixelchef">
        <h5>PixelChef</h5>
        <p class="tagline">A pixel-art chef simulator</p>
      </a>
      <a class="block-wrapper-link" href="/software/voxel-arena">
        <h5>Voxel Arena</h5>
        <p class="tagline">Battle royale in voxels</p>
      </a>
    </body></html>
    """
    result = _parse_software_listing(html, limit=10)
    assert len(result) == 2
    assert result[0]["project_name"] == "PixelChef"
    assert result[0]["devpost_url"].endswith("/software/pixelchef")


def test_parse_software_listing_dedup():
    html = """
    <html><body>
      <a class="block-wrapper-link" href="/software/x"><h5>X</h5></a>
      <a class="block-wrapper-link" href="/software/x"><h5>X</h5></a>
    </body></html>
    """
    result = _parse_software_listing(html, limit=10)
    assert len(result) == 1


def test_parse_project_page_extracts_github_and_prize():
    html = """
    <html><body>
      <h1 id="app-title">PixelChef</h1>
      <p class="large">A pixel chef simulator</p>
      <a href="https://github.com/x/pixelchef">github</a>
      <a class="app-links" href="https://pixelchef.io">demo</a>
      <li>🏆 Winner of Best Overall</li>
      <ul id="built-with"><li>python</li><li>ffmpeg</li></ul>
      <ul class="software-team-members"><li>Jane Doe</li><li>John Smith</li></ul>
    </body></html>
    """
    data = _parse_project_page(html)
    assert data["project_name"] == "PixelChef"
    assert data["github_url"] == "https://github.com/x/pixelchef"
    assert data["demo_url"] == "https://pixelchef.io"
    assert "Winner" in (data["prize"] or "")
    assert "python" in data["technologies"]
    assert "Jane Doe" in (data["team"] or "")


def test_devpost_scanner_filters_to_prize_with_github(tmp_db, mock_run_id):
    _seed_run(tmp_db, mock_run_id)
    from src.config import Settings
    from src.sources.devpost.scanner import scan_devpost

    fake_client = MagicMock()
    fake_client.list_recent_software.return_value = [
        {"devpost_url": "https://devpost.com/software/a", "project_name": "A"},
        {"devpost_url": "https://devpost.com/software/b", "project_name": "B"},
        {"devpost_url": "https://devpost.com/software/c", "project_name": "C"},
    ]
    fake_client.fetch_project.side_effect = [
        # A: has github + prize → eligible
        {
            "project_name": "A", "tagline": "tagline-a", "github_url": "https://github.com/x/a",
            "prize": "Best Overall", "team": "Jane", "technologies": ["python"],
            "demo_url": None, "hackathon_name": "HackMIT", "submitted_at": None, "description": None,
        },
        # B: github but no prize → ineligible (still upserted for tracking)
        {
            "project_name": "B", "github_url": "https://github.com/x/b", "prize": None,
            "team": None, "technologies": [], "demo_url": None, "hackathon_name": None,
            "submitted_at": None, "tagline": None, "description": None,
        },
        # C: prize but no github → ineligible
        {
            "project_name": "C", "github_url": None, "prize": "Most Creative",
            "team": None, "technologies": [], "demo_url": None, "hackathon_name": None,
            "submitted_at": None, "tagline": None, "description": None,
        },
    ]

    settings = Settings(gh_token="x", openai_api_key="sk-test")
    candidates = scan_devpost(tmp_db, settings, mock_run_id, client=fake_client)

    # Only A passes both filters
    assert len(candidates) == 1
    assert candidates[0].project_name == "A"

    # All three got upserted to hackathon_projects for future scans
    rows = tmp_db.execute("SELECT project_name FROM hackathon_projects").fetchall()
    assert {r["project_name"] for r in rows} == {"A", "B", "C"}
