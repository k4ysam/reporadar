from __future__ import annotations

from datetime import date
from pathlib import Path

from flask import Flask, render_template, send_from_directory

from src.common.config import Settings
from src.common.db import open_connection
from src.operator_api.web import queries


def create_app(settings: Settings) -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    output_dir_abs = str(Path(settings.output_dir).resolve())

    @app.template_global()
    def score_class(score: float | None) -> str:
        if score is None:
            return "score-none"
        if score >= 7.5:
            return "score-high"
        if score >= 5.0:
            return "score-mid"
        return "score-low"

    @app.route("/media/<path:filename>")
    def media(filename):
        """Serve rendered images from settings.output_dir.

        `send_from_directory` defends against path traversal: it refuses any
        `filename` that resolves outside `output_dir_abs`.
        """
        return send_from_directory(output_dir_abs, filename)

    @app.route("/")
    def dashboard():
        conn = open_connection(settings)
        try:
            return render_template(
                "dashboard.html",
                scans=queries.get_todays_scans(conn),
                hackathons=queries.get_recent_hackathons(conn),
                evaluations=queries.get_recent_evaluations(conn),
                posts=queries.get_recent_posts(conn),
                runs=queries.get_recent_runs(conn),
                today=date.today().isoformat(),
            )
        finally:
            conn.close()

    return app
