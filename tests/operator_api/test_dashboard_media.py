"""Tests for the /media/<filename> dashboard route + queries enrichment.

The dashboard needs to serve rendered JPEGs from settings.output_dir so the
template can `<img src=...>` them inline. Path traversal must not allow
escape from that directory.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from src.operator_api.web import queries
from src.operator_api.web.app import create_app


class _StubSettings:
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        self.database_url = "postgresql://stub"


def test_media_route_serves_file_from_output_dir(tmp_path: Path):
    (tmp_path / "poster.jpg").write_bytes(b"\xff\xd8\xff\xe0fake jpeg")
    settings = _StubSettings(str(tmp_path))

    app = create_app(settings)
    client = app.test_client()
    resp = client.get("/media/poster.jpg")
    assert resp.status_code == 200
    assert resp.data.startswith(b"\xff\xd8\xff")


def test_media_route_404s_on_missing_file(tmp_path: Path):
    settings = _StubSettings(str(tmp_path))
    app = create_app(settings)
    client = app.test_client()
    resp = client.get("/media/does-not-exist.jpg")
    assert resp.status_code == 404


def test_media_route_blocks_path_traversal(tmp_path: Path):
    # Create a secret file *outside* the output dir.
    secret = tmp_path.parent / "secret.txt"
    secret.write_text("nope")
    settings = _StubSettings(str(tmp_path))

    app = create_app(settings)
    client = app.test_client()
    # send_from_directory refuses paths that escape its base via 404 / 403.
    resp = client.get("/media/..%2Fsecret.txt")
    assert resp.status_code in (403, 404)


def test_get_recent_posts_projects_image_basename_and_caption(monkeypatch):
    """queries.get_recent_posts must include first_path_basename, caption,
    hashtags, source_links so the template can render the card."""
    fake_row = {
        "id": "posted_proj_1",
        "canonical_repo_url": "https://github.com/example/x",
        "github": {"full_name": "example/x", "url": "https://github.com/example/x"},
        "hackathon": None,
        "project_description": {"ai_summary": "A cool repo"},
        "post_instances": [
            {
                "post_id": "post_linkedin_abc",
                "platform": "linkedin",
                "status": "exported",
                "content": {
                    "text": "Long LinkedIn commentary here.",
                    "hook": "Quick hook",
                    "hashtags": ["opensource", "ai"],
                    "character_count": 32,
                    "content_format": "commentary",
                },
                "media": [
                    {
                        "asset_id": "asset_1",
                        "local_path": "output/linkedin_example-x_20260516.jpg",
                        "alt_text": "An accessible alt",
                        "width": 1024,
                        "height": 1536,
                    }
                ],
                "source_links": ["https://github.com/example/x"],
                "publication": {"external_post_url": None},
                "review": {"review_notes": None},
            }
        ],
        "posting_state": {"has_been_posted": False},
        "updated_at": None,
    }

    fake_cursor = MagicMock()
    fake_cursor.__enter__ = MagicMock(return_value=fake_cursor)
    fake_cursor.__exit__ = MagicMock(return_value=False)
    fake_cursor.execute = MagicMock()
    fake_cursor.fetchall = MagicMock(return_value=[fake_row])

    fake_conn = MagicMock()
    fake_conn.cursor = MagicMock(return_value=fake_cursor)

    posts = queries.get_recent_posts(fake_conn)
    assert len(posts) == 1
    p = posts[0]
    assert p["channel"] == "linkedin"
    assert p["caption"] == "Long LinkedIn commentary here."
    assert p["first_path_basename"] == "linkedin_example-x_20260516.jpg"
    assert p["first_alt_text"] == "An accessible alt"
    assert p["first_image_dims"] == "1024×1536"
    assert "opensource" in p["hashtags"]
    assert p["source_links"] == ["https://github.com/example/x"]
    assert p["summary"] == "A cool repo"
    assert p["subject_url"] == "https://github.com/example/x"
