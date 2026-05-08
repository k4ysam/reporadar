from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pytest

from src.db import init_db
from src.web.app import create_app


@pytest.fixture
def app(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    return create_app(db_path)


@pytest.fixture
def client(app):
    return app.test_client()


def test_dashboard_returns_200(client):
    resp = client.get("/")
    assert resp.status_code == 200


def test_dashboard_is_read_only(client):
    """No /scan POST endpoint anymore — pipeline is automated."""
    resp = client.post("/scan", data={"window_days": "3"})
    assert resp.status_code in (404, 405)


def test_dashboard_shows_scanned_repo(tmp_path):
    db_path = str(tmp_path / "seeded.db")
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO repos_seen (full_name, first_seen_at, last_scan_at, star_count_at_last_scan) "
        "VALUES (?, ?, ?, ?)",
        ("owner/myrepo", now, now, 500),
    )
    conn.commit()
    conn.close()

    app = create_app(db_path)
    html = app.test_client().get("/").data.decode()
    assert "owner/myrepo" in html
    assert "https://github.com/owner/myrepo" in html


def test_xss_escaped(tmp_path):
    db_path = str(tmp_path / "xss.db")
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO repos_seen (full_name, first_seen_at, last_scan_at) VALUES (?, ?, ?)",
        ("<script>alert(1)</script>", now, now),
    )
    conn.commit()
    conn.close()
    html = create_app(db_path).test_client().get("/").data.decode()
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
