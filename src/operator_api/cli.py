from __future__ import annotations

import argparse
import sys
from pathlib import Path

from datetime import datetime, timezone

from src.ai_gateway.factory import get_llm_provider
from src.candidate_intelligence.enrichment import enrich_github_candidate
from src.candidate_intelligence.evaluation import synthesize_evaluation_for_manual
from src.candidate_intelligence.repository import set_evaluation, upsert_candidate
from src.candidate_intelligence.service import (
    discover_and_evaluate,
    evaluate_pending_candidates,
)
from src.candidate_intelligence.source_adapters.devpost_discovery.scanner import scan_devpost
from src.candidate_intelligence.source_adapters.github_discovery.client import GithubClient
from src.candidate_intelligence.source_adapters.github_discovery.scanner import scan_github
from src.candidate_intelligence.source_adapters.manual_submission import submit_manual
from src.common.config import Settings
from src.common.db import connect
from src.common.ids import selection_id
from src.common.logger import get_logger
from src.content_generation import generate_post_package
from src.contracts.selection import RankingBreakdown, SelectionDecision
from src.orchestrator.pipeline import run_pipeline
from src.orchestrator.runs import finish_run, start_run
from src.publishing import publish_packages


def cmd_scan_repos(args, settings: Settings) -> int:
    with connect(settings) as conn:
        run_id = start_run(conn, run_type="scan_repos")
        log = get_logger("reporadar.scan-repos", run_id)
        try:
            candidates = scan_github(conn, settings, run_id)
            finish_run(conn, run_id)
            if not candidates:
                print("No rising repos this run.")
                return 0
            print(f"\n{'Repo':<45} {'Stars':>6} {'Growth':>8}  Lang")
            print("-" * 80)
            for c in candidates:
                gh = c.github
                growth = c.discovery.growth_percent if c.discovery else 0
                print(
                    f"{gh.full_name:<45} {gh.stars_count:>6} {growth:>7.0f}%  {gh.primary_language or '—'}"
                )
            return 0
        except Exception as exc:
            finish_run(conn, run_id, error=str(exc))
            log.error("Scan failed: %s", exc)
            return 1


def cmd_scan_hackathons(args, settings: Settings) -> int:
    with connect(settings) as conn:
        run_id = start_run(conn, run_type="scan_hackathons")
        log = get_logger("reporadar.scan-hackathons", run_id)
        try:
            candidates = scan_devpost(conn, settings, run_id)
            finish_run(conn, run_id)
            if not candidates:
                print("No hackathon candidates this run.")
                return 0
            print(f"\n{'Project':<45} {'Hackathon':<25} Prize")
            print("-" * 95)
            for c in candidates:
                h = c.hackathon
                print(
                    f"{h.project_name[:44]:<45} {(h.hackathon_name or '—')[:24]:<25} {(h.prize or '—')[:30]}"
                )
            return 0
        except Exception as exc:
            finish_run(conn, run_id, error=str(exc))
            log.error("Hackathon scan failed: %s", exc)
            return 1


def cmd_evaluate(args, settings: Settings) -> int:
    with connect(settings) as conn:
        run_id = start_run(conn, run_type="evaluate")
        log = get_logger("reporadar.evaluate", run_id)
        try:
            provider = get_llm_provider(settings, conn, run_id)
            evals = evaluate_pending_candidates(conn, settings, run_id, provider)
            finish_run(conn, run_id)
            if not evals:
                print("No pending candidates to evaluate.")
                return 0
            for ev in evals:
                print(
                    f"[{ev.provider}] {ev.candidate_id:<20} "
                    f"N={ev.scores.novelty} E={ev.scores.explainability} "
                    f"O={ev.scores.overall}{'  SKIP' if ev.skip else ''}"
                )
            return 0
        except Exception as exc:
            finish_run(conn, run_id, error=str(exc))
            log.error("Evaluate failed: %s", exc)
            return 1


def cmd_run(args, settings: Settings) -> int:
    log = get_logger("reporadar.run", "manual")
    channels = args.channels.split(",") if args.channels else None
    with connect(settings) as conn:
        try:
            result = run_pipeline(conn, settings, channels=channels)
            if result is None:
                print("Pipeline finished without saving a post (nothing eligible).")
                return 0
            print(f"Run {result['run_id']} → posted_id {result['posted_id']}")
            print(f"  Selection score: {result['selection_score']}")
            print(f"  Channels: {', '.join(result['channels'])}")
            print("  Images:")
            for p in result["image_paths"]:
                print(f"    {p}")
            print("  Exports:")
            for p in result["export_paths"]:
                print(f"    {p}")
            return 0
        except Exception as exc:
            log.error("Run failed: %s", exc)
            print(f"FAILED: {exc}", file=sys.stderr)
            return 1


def cmd_submit(args, settings: Settings) -> int:
    """Manually submit a project URL and generate ready-for-review posts.

    Skips the LLM evaluation phase entirely — operator submission is an
    implicit "feature this". The flow is:

        1. submit_manual            (write candidate row from GitHub/Devpost)
        2. enrich_github_candidate  (README + commits + issues, GitHub only)
        3. synthesize_evaluation    (placeholder Evaluation, no LLM scoring)
        4. forced SelectionDecision (no ranking pool — operator chose this row)
        5. generate_post_package    (per channel: text → media → packaging)
        6. publish_packages         (write posted_repositories row + sidecar JSON)

    The result is one or more PostPackages in `posted_repositories` with
    status="exported", visible in the dashboard's "Posts awaiting review".
    """
    channels = (
        [c.strip() for c in args.channels.split(",") if c.strip()]
        if args.channels
        else ["instagram", "linkedin"]
    )

    with connect(settings) as conn:
        run_id = start_run(conn, run_type="manual_submission", requested_by="operator")
        log = get_logger("reporadar.submit", run_id)
        try:
            # 1. Discover via manual_submission adapter.
            candidate = submit_manual(conn, settings, run_id, args.url)
            print(
                f"Submitted candidate {candidate.candidate_id} "
                f"({candidate.canonical_repo_key})"
            )

            # 2. Enrich GitHub candidates so synthesize_evaluation has README signal.
            if candidate.github:
                gh_client = GithubClient(conn, run_id, settings.gh_token)
                enrichment = enrich_github_candidate(candidate.github.full_name, gh_client)
                candidate = candidate.model_copy(update={"enrichment": enrichment})
                upsert_candidate(conn, candidate)

            # 3. Synthesize Evaluation (no LLM scoring) and persist it on the
            #    candidate row so the dashboard's evaluations section also shows it.
            evaluation = synthesize_evaluation_for_manual(candidate)
            set_evaluation(
                conn,
                candidate_id=candidate.candidate_id,
                evaluation_payload=evaluation.model_dump(mode="json"),
                skip=False,
            )

            # 4. Forced SelectionDecision — operator's pick, no ranking pool.
            selection = SelectionDecision(
                selection_id=selection_id(),
                candidate_id=candidate.candidate_id,
                project_id=candidate.project_id,
                run_id=run_id,
                ranking_version="manual_v1",
                ranking_score=9.0,
                rank_in_run=1,
                total_candidates_in_run=1,
                score_breakdown=RankingBreakdown(evaluation_overall_score=9.0),
                ranking_reasons=["Manually submitted by operator."],
                eligible=True,
                selected=True,
                selected_for_channels=channels,
                selected_at=datetime.now(timezone.utc),
            )

            # 5. Content Generation per channel.
            provider = get_llm_provider(settings, conn, run_id)
            packages = []
            for channel in channels:
                try:
                    package = generate_post_package(
                        conn, settings, run_id, candidate, evaluation, provider, channel=channel
                    )
                    packages.append(package)
                except Exception as exc:
                    log.exception("Channel %s failed: %s", channel, exc)
                    print(f"  Channel {channel} failed: {exc}", file=sys.stderr)

            if not packages:
                finish_run(conn, run_id, error="All channels failed")
                return 1

            # 6. Publish (posted_repositories row + sidecar JSONs to output_dir).
            posted_id, json_paths = publish_packages(
                conn,
                settings,
                candidate=candidate,
                evaluation=evaluation,
                selection=selection,
                packages=packages,
            )

            finish_run(conn, run_id)
            print(f"\nGenerated {len(packages)} post(s) ready for review → posted_id {posted_id}")
            for package in packages:
                print(f"  [{package.channel}] caption ({package.content.character_count} chars)")
                for asset in package.media:
                    print(f"    image: {asset.local_path}")
            print("\nReview in dashboard: python -m src serve")
            return 0
        except Exception as exc:
            finish_run(conn, run_id, error=str(exc))
            log.error("Submit failed: %s", exc)
            print(f"FAILED: {exc}", file=sys.stderr)
            return 1


def cmd_serve(args, settings: Settings) -> int:
    from src.operator_api.web.app import create_app

    app = create_app(settings)
    host = getattr(args, "host", "127.0.0.1")
    port = getattr(args, "port", 8000)
    debug = getattr(args, "debug", False)
    print(f"Read-only dashboard at http://{host}:{port} — Ctrl+C to stop")
    app.run(host=host, port=port, debug=debug)
    return 0


def cmd_daemon(args, settings: Settings) -> int:
    from src.scheduler.daemon import run_forever

    run_forever(settings)
    return 0


def cmd_verify_env(args, settings: Settings) -> int:
    with connect(settings) as conn:
        run_id = start_run(conn, run_type="verify_env")
        print(f"LLM_PROVIDER={settings.llm_provider}")
        issues: list[str] = []

        try:
            gh = GithubClient(conn, run_id, settings.gh_token)
            rate = gh.get_rate_limit()
            remaining = rate["resources"]["core"]["remaining"]
            print(f"GitHub OK — {remaining}/5000 core requests remaining")
        except Exception as exc:
            issues.append(f"GitHub: {exc}")

        try:
            provider = get_llm_provider(settings, conn, run_id)
            sample = provider.generate("Reply with the single word OK.", system="Be terse.")
            print(f"LLM ({provider.name}) OK — sample: {sample[:60]!r}")
        except Exception as exc:
            issues.append(f"LLM: {exc}")

        out = Path(settings.output_dir)
        try:
            out.mkdir(parents=True, exist_ok=True)
            print(f"Output dir OK — {out.resolve()}")
        except Exception as exc:
            issues.append(f"Output dir: {exc}")

        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            print("Postgres OK")
        except Exception as exc:
            issues.append(f"Postgres: {exc}")

        if issues:
            print("\nIssues:")
            for msg in issues:
                print(f"  - {msg}")
            finish_run(conn, run_id, error="; ".join(issues))
            return 1
        finish_run(conn, run_id)
        print("\nAll checks passed.")
        return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="reporadar", description="RepoRadar pipeline")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("scan-repos", help="Scan GitHub for rising repos")
    sub.add_parser("scan-hackathons", help="Scrape Devpost for prize-winning hackathon projects")
    sub.add_parser("evaluate", help="Evaluate pending candidates with the LLM")

    run_p = sub.add_parser("run", help="Run the full pipeline across all sources + channels")
    run_p.add_argument(
        "--channels",
        default=None,
        help="Comma-separated list of channels (default: instagram,linkedin)",
    )

    submit_p = sub.add_parser(
        "submit",
        help="Submit a URL and generate ready-for-review posts (skips LLM evaluation)",
    )
    submit_p.add_argument("url")
    submit_p.add_argument(
        "--channels",
        default=None,
        help="Comma-separated list of channels (default: instagram,linkedin)",
    )

    serve_p = sub.add_parser("serve", help="Start the read-only monitoring dashboard")
    serve_p.add_argument("--host", default="127.0.0.1")
    serve_p.add_argument("--port", type=int, default=8000)
    serve_p.add_argument("--debug", action="store_true")

    sub.add_parser("daemon", help="Start the APScheduler daemon")
    sub.add_parser("verify-env", help="Ping all configured external services")

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0

    try:
        settings = Settings.from_env()
    except (RuntimeError, ValueError) as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1

    dispatch = {
        "scan-repos": cmd_scan_repos,
        "scan-hackathons": cmd_scan_hackathons,
        "evaluate": cmd_evaluate,
        "run": cmd_run,
        "submit": cmd_submit,
        "serve": cmd_serve,
        "daemon": cmd_daemon,
        "verify-env": cmd_verify_env,
    }
    return dispatch[args.command](args, settings)


if __name__ == "__main__":
    sys.exit(main())
