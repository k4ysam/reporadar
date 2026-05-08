from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.publisher.instagram import InstagramClient, InstagramError


def _seed_run(db, run_id):
    db.execute(
        "INSERT INTO pipeline_runs (run_id, started_at, status) VALUES (?, '2026-05-01', 'running')",
        (run_id,),
    )
    db.commit()


def _client(tmp_db, run_id, session):
    return InstagramClient(tmp_db, run_id, "TOKEN", "IGUSER", session=session)


def test_post_single_full_flow(tmp_db, mock_run_id):
    _seed_run(tmp_db, mock_run_id)
    session = MagicMock()
    container_resp = MagicMock(ok=True, status_code=200, text="", json=lambda: {"id": "ctn1"})
    finished_resp = MagicMock(ok=True, status_code=200, text="", json=lambda: {"status_code": "FINISHED"})
    publish_resp = MagicMock(ok=True, status_code=200, text="", json=lambda: {"id": "media123"})
    permalink_resp = MagicMock(ok=True, status_code=200, text="", json=lambda: {"permalink": "https://i/g/p/123"})
    session.request.side_effect = [container_resp, finished_resp, publish_resp, permalink_resp]

    client = _client(tmp_db, mock_run_id, session)
    result = client.post_single("https://x/y.jpg", "caption")
    assert result["media_id"] == "media123"
    assert result["permalink"].endswith("/123")


def test_carousel_requires_two_to_ten(tmp_db, mock_run_id):
    _seed_run(tmp_db, mock_run_id)
    client = _client(tmp_db, mock_run_id, MagicMock())
    with pytest.raises(InstagramError, match="2.+10"):
        client.post_carousel(["https://x"], "cap")


def test_publish_failure_raises(tmp_db, mock_run_id):
    _seed_run(tmp_db, mock_run_id)
    session = MagicMock()
    session.request.return_value = MagicMock(ok=False, status_code=400, text="bad request")
    client = _client(tmp_db, mock_run_id, session)
    with pytest.raises(InstagramError):
        client.create_image_container("https://x", "cap")
