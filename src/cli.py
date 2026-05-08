from __future__ import annotations

import argparse
import sqlite3
import sys
import uuid
from datetime import datetime, timezone


def _start_run(db: sqlite3.Connection) -> str:
    run_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO pipeline_runs (run_id, started_at, status) VALUES (?, ?, 'running')",
        (run_id, datetime.now(timezone.utc).isoformat()),
    )
    db.commit()
    return run_id


def _finish_run(db: sqlite3.Connection, run_id: str, error: str | None = None) -> None:
    if error:
        db.execute(
            "UPDATE pipeline_runs SET status='failed', completed_at=?, error_message=? WHERE run_id=?",
            (datetime.now(timezone.utc).isoformat(), error[:500], run_id),
        )
    else:
        db.execute(
            "UPDATE pipeline_runs SET status='completed', completed_at=? WHERE run_id=?",
            (datetime.now(timezone.utc).isoformat(), run_id),
        )
    db.commit()


def cmd_scan_repos(args, settings, db: sqlite3.Connection) -> int:
    from src.logger import get_logger
    from src.sources.github_repos.scanner import scan as scan_repos

    run_id = _start_run(db)
    log = get_logger("reporadar.scan-repos", run_id)
    try:
        candidates = scan_repos(db, settings, run_id)
        _finish_run(db, run_id)
        if not candidates:
            print("No rising repos this run.")
            return 0
        print(f"\n{'Repo':<45} {'Stars':>6} {'Growth':>8}  Lang")
        print("-" * 80)
        for c in candidates:
            print(f"{c.full_name:<45} {c.stars_now:>6} {c.growth_pct:>7.0f}%  {c.language or '—'}")
        return 0
    except Exception as exc:
        _finish_run(db, run_id, error=str(exc))
        log.error("Scan failed: %s", exc)
        return 1


def cmd_scan_hackathons(args, settings, db: sqlite3.Connection) -> int:
    from src.logger import get_logger
    from src.sources.devpost.scanner import scan_devpost

    run_id = _start_run(db)
    log = get_logger("reporadar.scan-hackathons", run_id)
    try:
        candidates = scan_devpost(db, settings, run_id)
        _finish_run(db, run_id)
        if not candidates:
            print("No hackathon candidates this run.")
            return 0
        print(f"\n{'Project':<45} {'Hackathon':<25} Prize")
        print("-" * 95)
        for c in candidates:
            print(f"{c.project_name[:44]:<45} {(c.hackathon_name or '—')[:24]:<25} {(c.prize or '—')[:30]}")
        return 0
    except Exception as exc:
        _finish_run(db, run_id, error=str(exc))
        log.error("Hackathon scan failed: %s", exc)
        return 1


def cmd_evaluate(args, settings, db: sqlite3.Connection) -> int:
    from datetime import datetime as dt
    from datetime import timezone as tz

    from src.evaluator.batch import evaluate_candidates, evaluate_hackathon_candidates
    from src.llm.provider import get_provider
    from src.logger import get_logger
    from src.models import Candidate, HackathonCandidate
    from src.sources.github_repos.client import GithubClient

    run_id = _start_run(db)
    log = get_logger("reporadar.evaluate", run_id)
    try:
        provider = get_provider(settings, db, run_id)
        gh_client = GithubClient(db, run_id, settings.gh_token)

        # repos
        repo_rows = db.execute(
            """
            SELECT id, full_name, star_count_at_last_scan, first_seen_at, github_repo_id
            FROM repos_seen
            WHERE already_posted = 0
              AND NOT EXISTS (
                SELECT 1 FROM evaluations e WHERE e.repo_id = repos_seen.id
              )
            ORDER BY last_scan_at DESC
            LIMIT ?
            """,
            (settings.max_evaluations_per_run * 3,),
        ).fetchall()
        repo_candidates: list[Candidate] = []
        for row in repo_rows:
            try:
                repo_candidates.append(
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
        repo_evals = evaluate_candidates(repo_candidates, provider, gh_client, db, run_id, settings)

        # hackathons
        hack_rows = db.execute(
            """
            SELECT * FROM hackathon_projects
            WHERE already_posted = 0
              AND github_url IS NOT NULL
              AND prize IS NOT NULL
              AND NOT EXISTS (
                SELECT 1 FROM evaluations e WHERE e.hackathon_id = hackathon_projects.id
              )
            ORDER BY last_scan_at DESC
            LIMIT ?
            """,
            (settings.max_evaluations_per_run * 3,),
        ).fetchall()
        hack_candidates: list[HackathonCandidate] = []
        for row in hack_rows:
            try:
                hack_candidates.append(
                    HackathonCandidate(
                        devpost_url=row["devpost_url"],
                        project_name=row["project_name"],
                        tagline=row["tagline"],
                        hackathon_name=row["hackathon_name"],
                        prize=row["prize"],
                        team=row["team"],
                        github_url=row["github_url"],
                        demo_url=row["demo_url"],
                        first_seen_at=dt.fromisoformat(row["first_seen_at"]),
                    )
                )
            except Exception:
                continue
        hack_evals = evaluate_hackathon_candidates(hack_candidates, provider, db, run_id, settings)

        _finish_run(db, run_id)

        if not repo_evals and not hack_evals:
            print("No evaluations produced.")
            return 0
        for ev in (repo_evals + hack_evals):
            print(f"[{ev.content_type}] {ev.full_name:<40} N={ev.novelty_score} E={ev.explainability_score} O={ev.overall_score}{'  SKIP' if ev.skip else ''}")
        return 0
    except Exception as exc:
        _finish_run(db, run_id, error=str(exc))
        log.error("Evaluate failed: %s", exc)
        return 1


def cmd_run(args, settings, db: sqlite3.Connection) -> int:
    """Run the full pipeline for today's content type."""
    from src.logger import get_logger
    from src.pipeline import run_for_today

    log = get_logger("reporadar.run", "manual")
    day = args.day if args.day is not None else None
    try:
        result = run_for_today(db, settings, day_of_week=day)
        if result is None:
            print("Pipeline finished without publishing (nothing eligible or non-publish day).")
            return 0
        print(f"Published: post_id={result.post_id} permalink={result.instagram_permalink}")
        return 0
    except Exception as exc:
        log.error("Run failed: %s", exc)
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1


def cmd_serve(args, settings, db: sqlite3.Connection) -> int:
    from src.web.app import create_app

    db.close()
    app = create_app(settings.db_path)
    host = getattr(args, "host", "127.0.0.1")
    port = getattr(args, "port", 8000)
    debug = getattr(args, "debug", False)
    print(f"Read-only dashboard at http://{host}:{port} — Ctrl+C to stop")
    app.run(host=host, port=port, debug=debug)
    return 0


def cmd_daemon(args, settings, db: sqlite3.Connection) -> int:
    from src.scheduler.daemon import run_forever

    db.close()
    run_forever(settings)
    return 0


def cmd_verify_env(args, settings, db: sqlite3.Connection) -> int:
    from src.publisher.token_manager import check_and_alert
    from src.sources.github_repos.client import GithubClient

    print(f"LLM_PROVIDER={settings.llm_provider}")
    issues: list[str] = []

    # GitHub
    try:
        gh = GithubClient(db, "verify", settings.gh_token)
        rate = gh.get_rate_limit()
        remaining = rate["resources"]["core"]["remaining"]
        print(f"GitHub OK — {remaining}/5000 core requests remaining")
    except Exception as exc:
        issues.append(f"GitHub: {exc}")

    # LLM
    try:
        from src.llm.provider import get_provider

        provider = get_provider(settings, db, "verify")
        sample = provider.generate("Reply with the single word OK.", system="Be terse.")
        print(f"LLM ({provider.name}) OK — sample: {sample[:60]!r}")
    except Exception as exc:
        issues.append(f"LLM: {exc}")

    # IG token
    if settings.ig_access_token:
        try:
            status = check_and_alert(settings)
            print(f"IG token: {status}")
        except Exception as exc:
            issues.append(f"IG token: {exc}")
    else:
        print("IG token: not configured (skipping)")

    # Image host
    if settings.image_host_bucket:
        try:
            from src.publisher.image_host import S3Host

            S3Host(settings)
            print(f"Image host OK — bucket={settings.image_host_bucket}")
        except Exception as exc:
            issues.append(f"Image host: {exc}")
    else:
        print("Image host: not configured (LocalFileHost will be used; not IG-compatible)")

    if issues:
        print("\nIssues:")
        for msg in issues:
            print(f"  - {msg}")
        return 1
    print("\nAll checks passed.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="reporadar", description="RepoRadar pipeline")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("scan-repos", help="Scan GitHub for rising repos")
    sub.add_parser("scan-hackathons", help="Scrape Devpost for prize-winning hackathon projects")
    sub.add_parser("evaluate", help="Evaluate any unevaluated repos and hackathons with the LLM")

    run_p = sub.add_parser("run", help="Run today's pipeline (Mon/Fri repo, Wed hackathon)")
    run_p.add_argument("--day", type=int, default=None, help="0=Mon … 6=Sun (overrides today)")

    serve_p = sub.add_parser("serve", help="Start the read-only monitoring dashboard")
    serve_p.add_argument("--host", default="127.0.0.1")
    serve_p.add_argument("--port", type=int, default=8000)
    serve_p.add_argument("--debug", action="store_true")

    sub.add_parser("daemon", help="Start the APScheduler daemon")
    sub.add_parser("verify-env", help="Ping all configured external services")

    # legacy aliases
    sub.add_parser("scan", help="Alias for scan-repos")

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0

    from src.config import Settings
    from src.db import get_db, init_db

    try:
        settings = Settings.from_env()
    except (RuntimeError, ValueError) as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1

    init_db(settings.db_path)
    db = get_db(settings.db_path)

    dispatch = {
        "scan-repos": cmd_scan_repos,
        "scan": cmd_scan_repos,  # legacy alias
        "scan-hackathons": cmd_scan_hackathons,
        "evaluate": cmd_evaluate,
        "run": cmd_run,
        "serve": cmd_serve,
        "daemon": cmd_daemon,
        "verify-env": cmd_verify_env,
    }
    return dispatch[args.command](args, settings, db)


if __name__ == "__main__":
    sys.exit(main())
