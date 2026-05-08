from __future__ import annotations

import sqlite3
from datetime import date

from flask import Flask, render_template

from src.web import queries


def create_app(db_path: str) -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")

    def _conn() -> sqlite3.Connection:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @app.template_global()
    def score_class(score: float | None) -> str:
        if score is None:
            return "score-none"
        if score >= 7.5:
            return "score-high"
        if score >= 5.0:
            return "score-mid"
        return "score-low"

    @app.route("/")
    def dashboard():
        with _conn() as conn:
            return render_template(
                "dashboard.html",
                scans=queries.get_todays_scans(conn),
                hackathons=queries.get_recent_hackathons(conn),
                evaluations=queries.get_recent_evaluations(conn),
                posts=queries.get_recent_posts(conn),
                runs=queries.get_recent_runs(conn),
                today=date.today().isoformat(),
            )

    return app
