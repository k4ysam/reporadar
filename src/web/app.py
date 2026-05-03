from __future__ import annotations

import sqlite3
import uuid
from datetime import date, datetime, timezone

from flask import Flask, redirect, render_template, request, url_for

from src.web import queries


def create_app(db_path: str, settings=None) -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.secret_key = "reporadar-local"

    def _conn() -> sqlite3.Connection:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _window_days(conn: sqlite3.Connection) -> int:
        from src.db import get_app_setting
        val = get_app_setting(conn, "velocity_window_hours")
        if val:
            return max(1, int(val) // 24)
        return (settings.velocity_window_hours // 24) if settings else 3

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
                evaluations=queries.get_evaluations_for_today(conn),
                runs=queries.get_recent_runs(conn),
                today=date.today().isoformat(),
                window_days=_window_days(conn),
                message=request.args.get("message"),
                error=request.args.get("error"),
            )

    @app.route("/scan", methods=["POST"])
    def run_scan():
        if settings is None:
            return redirect(url_for("dashboard", error="Server started without settings — use python -m src serve"))

        window_days = int(request.form.get("window_days", 3))
        window_hours = window_days * 24
        run_settings = settings.model_copy(update={"velocity_window_hours": window_hours})

        with _conn() as conn:
            from src.db import set_app_setting
            set_app_setting(conn, "velocity_window_hours", str(window_hours))

            run_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO pipeline_runs (run_id, started_at, status) VALUES (?, ?, 'running')",
                (run_id, datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()

            try:
                from src.scanner.scanner import scan
                candidates = scan(conn, run_settings, run_id)
                conn.execute(
                    "UPDATE pipeline_runs SET status='completed', completed_at=? WHERE run_id=?",
                    (datetime.now(timezone.utc).isoformat(), run_id),
                )
                conn.commit()
                return redirect(url_for("dashboard", message=f"Scan complete — {len(candidates)} candidate(s) found."))
            except Exception as exc:
                conn.execute(
                    "UPDATE pipeline_runs SET status='failed', completed_at=?, error_message=? WHERE run_id=?",
                    (datetime.now(timezone.utc).isoformat(), str(exc), run_id),
                )
                conn.commit()
                return redirect(url_for("dashboard", error=str(exc)[:200]))

    return app
