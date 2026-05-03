from __future__ import annotations

import argparse
import sqlite3
import sys
import uuid
from datetime import datetime, timezone


def cmd_scan(args, settings, db: sqlite3.Connection) -> int:
    from src.scanner.scanner import scan
    from src.logger import get_logger

    run_id = str(uuid.uuid4())
    log = get_logger("reporadar.scan", run_id)
    db.execute(
        "INSERT INTO pipeline_runs (run_id, started_at, status) VALUES (?, ?, 'running')",
        (run_id, datetime.now(timezone.utc).isoformat()),
    )
    db.commit()
    try:
        log.info("Starting scan")
        candidates = scan(db, settings, run_id)
        db.execute(
            "UPDATE pipeline_runs SET status='completed', completed_at=? WHERE run_id=?",
            (datetime.now(timezone.utc).isoformat(), run_id),
        )
        db.commit()
        if not candidates:
            print("No candidates found today — thresholds may be too strict, or no active repos detected.")
            return 0
        print(f"\n{'Repo':<45} {'Stars':>6}  {'Growth':>8}  {'Language':<12}")
        print("-" * 80)
        for c in candidates:
            print(f"{c.full_name:<45} {c.stars_now:>6}  {c.growth_pct:>7.0f}%  {c.language or '—':<12}")
        print(f"\n{len(candidates)} candidate(s) found. Run `python -m src evaluate` to evaluate them.")
        return 0
    except Exception as exc:
        db.execute(
            "UPDATE pipeline_runs SET status='failed', completed_at=?, error_message=? WHERE run_id=?",
            (datetime.now(timezone.utc).isoformat(), str(exc), run_id),
        )
        db.commit()
        log.error("Scan failed: %s", exc)
        return 1


def cmd_evaluate(args, settings, db: sqlite3.Connection) -> int:
    import anthropic
    from src.evaluator.batch import evaluate_candidates
    from src.scanner.github_client import GithubClient
    from src.logger import get_logger

    run_id = str(uuid.uuid4())
    log = get_logger("reporadar.evaluate", run_id)
    db.execute(
        "INSERT INTO pipeline_runs (run_id, started_at, status) VALUES (?, ?, 'running')",
        (run_id, datetime.now(timezone.utc).isoformat()),
    )
    db.commit()
    try:
        from src.models import Candidate
        from datetime import datetime as dt

        rows = db.execute(
            """
            SELECT r.id, r.full_name, r.star_count_at_last_scan, r.first_seen_at,
                   r.github_repo_id
            FROM repos_seen r
            WHERE r.already_posted = 0
              AND NOT EXISTS (
                SELECT 1 FROM evaluations e WHERE e.repo_id = r.id
              )
            ORDER BY r.last_scan_at DESC
            LIMIT ?
            """,
            (settings.max_evaluations_per_run * 3,),
        ).fetchall()

        if not rows:
            print("No unevaluated repos found. Run `python -m src scan` first.")
            return 0

        from datetime import timezone as tz
        candidates = []
        for row in rows:
            try:
                candidates.append(
                    Candidate(
                        repo_id=row["github_repo_id"] or row["id"],
                        full_name=row["full_name"],
                        stars_now=row["star_count_at_last_scan"],
                        stars_48h_ago=0,
                        growth_pct=0.0,
                        created_at=dt.now(tz.utc),
                        first_seen_at=dt.fromisoformat(row["first_seen_at"]),
                    )
                )
            except Exception:
                continue

        gh_client = GithubClient(db, run_id, settings.gh_token)
        anthropic_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

        log.info("Evaluating %d candidates", len(candidates))
        evaluations = evaluate_candidates(candidates, anthropic_client, gh_client, db, run_id, settings)

        db.execute(
            "UPDATE pipeline_runs SET status='completed', completed_at=? WHERE run_id=?",
            (datetime.now(timezone.utc).isoformat(), run_id),
        )
        db.commit()

        if not evaluations:
            print("No evaluations produced.")
            return 0

        print(f"\n{'Repo':<45} {'N':>4} {'E':>4} {'O':>4}")
        print("-" * 60)
        for e in evaluations:
            print(f"{e.full_name:<45} {e.novelty_score:>4.1f} {e.explainability_score:>4.1f} {e.overall_score:>4.1f}")
            print(f"  {e.summary[:100]}")
            print()

        print(f"Run `python -m src serve` to view results in the dashboard.")
        return 0
    except Exception as exc:
        db.execute(
            "UPDATE pipeline_runs SET status='failed', completed_at=?, error_message=? WHERE run_id=?",
            (datetime.now(timezone.utc).isoformat(), str(exc), run_id),
        )
        db.commit()
        log.error("Evaluate failed: %s", exc)
        return 1


def cmd_serve(args, settings, db: sqlite3.Connection) -> int:
    from src.web.app import create_app

    db.close()
    app = create_app(settings.db_path)
    host = getattr(args, "host", "127.0.0.1")
    port = getattr(args, "port", 8000)
    debug = getattr(args, "debug", False)
    print(f"Dashboard running at http://{host}:{port} — Ctrl+C to stop")
    app.run(host=host, port=port, debug=debug)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="reporadar", description="RepoRadar pipeline")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("scan", help="Scan GitHub for rising repos")
    sub.add_parser("evaluate", help="Evaluate candidates with Claude")

    serve_p = sub.add_parser("serve", help="Start the web dashboard")
    serve_p.add_argument("--host", default="127.0.0.1")
    serve_p.add_argument("--port", type=int, default=8000)
    serve_p.add_argument("--debug", action="store_true")

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0

    from src.config import Settings
    from src.db import get_db, init_db

    try:
        settings = Settings.from_env()
    except RuntimeError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1

    init_db(settings.db_path)
    db = get_db(settings.db_path)

    dispatch = {"scan": cmd_scan, "evaluate": cmd_evaluate, "serve": cmd_serve}
    return dispatch[args.command](args, settings, db)


if __name__ == "__main__":
    sys.exit(main())
