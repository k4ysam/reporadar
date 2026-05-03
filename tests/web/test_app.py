from __future__ import annotations

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


def test_dashboard_empty_state_messages(client):
    html = client.get("/").data.decode()
    assert "python -m src scan" in html
    assert "python -m src evaluate" in html


def test_dashboard_shows_scanned_repo(tmp_path):
    import sqlite3
    from datetime import datetime, timezone

    db_path = str(tmp_path / "seeded.db")
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO repos_seen (full_name, first_seen_at, last_scan_at, star_count_at_last_scan) VALUES (?, ?, ?, ?)",
        ("owner/myrepo", now, now, 500),
    )
    conn.commit()
    conn.close()

    app = create_app(db_path)
    resp = app.test_client().get("/")
    html = resp.data.decode()
    assert "owner/myrepo" in html
    assert "https://github.com/owner/myrepo" in html


def test_xss_escaped(tmp_path):
    import sqlite3
    from datetime import datetime, timezone

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

    app = create_app(db_path)
    html = app.test_client().get("/").data.decode()
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
