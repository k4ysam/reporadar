from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from src.config import Settings
from src.models import HackathonCandidate
from src.sources.devpost.client import DevpostClient


def scan_devpost(
    db: sqlite3.Connection,
    config: Settings,
    run_id: str,
    client: DevpostClient | None = None,
) -> list[HackathonCandidate]:
    """Scan Devpost for recent prize-winning projects with a GitHub link.

    Per the PRD: hackathon source filters by prize-winning status + GitHub link.
    """
    client = client or DevpostClient(db, run_id)

    listings = client.list_recent_software(limit=config.devpost_max_projects_per_run)
    if not listings:
        return []

    now_iso = datetime.now(timezone.utc).isoformat()
    candidates: list[HackathonCandidate] = []

    for listing in listings:
        url = listing["devpost_url"]
        existing = db.execute(
            "SELECT id, already_posted, excluded_until FROM hackathon_projects WHERE devpost_url = ?",
            (url,),
        ).fetchone()
        if existing and existing["already_posted"]:
            continue
        if existing and existing["excluded_until"]:
            try:
                excl = datetime.fromisoformat(existing["excluded_until"]).date()
                if excl >= datetime.now(timezone.utc).date():
                    continue
            except Exception:
                pass

        details = client.fetch_project(url)
        if not details:
            continue

        # PRD filter: must have GitHub link + prize-winning status
        if not details.get("github_url"):
            _upsert(db, url, details, listing, now_iso)
            continue
        if not details.get("prize"):
            _upsert(db, url, details, listing, now_iso)
            continue

        _upsert(db, url, details, listing, now_iso)
        first_seen_iso = (
            db.execute("SELECT first_seen_at FROM hackathon_projects WHERE devpost_url=?", (url,))
            .fetchone()["first_seen_at"]
        )
        try:
            first_seen_at = datetime.fromisoformat(first_seen_iso)
        except Exception:
            first_seen_at = datetime.now(timezone.utc)

        candidates.append(
            HackathonCandidate(
                devpost_url=url,
                project_name=details.get("project_name") or listing.get("project_name") or "Untitled",
                tagline=details.get("tagline") or listing.get("tagline"),
                hackathon_name=details.get("hackathon_name"),
                prize=details.get("prize"),
                team=details.get("team"),
                github_url=details.get("github_url"),
                demo_url=details.get("demo_url"),
                submitted_at=details.get("submitted_at"),
                first_seen_at=first_seen_at,
                description=details.get("description"),
                technologies=details.get("technologies", []),
            )
        )

    return candidates


def _upsert(db: sqlite3.Connection, url: str, details: dict, listing: dict, now_iso: str) -> None:
    db.execute(
        """
        INSERT INTO hackathon_projects (
            devpost_url, project_name, tagline, hackathon_name, prize, team,
            github_url, demo_url, submitted_at, first_seen_at, last_scan_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(devpost_url) DO UPDATE SET
            project_name   = excluded.project_name,
            tagline        = excluded.tagline,
            hackathon_name = excluded.hackathon_name,
            prize          = excluded.prize,
            team           = excluded.team,
            github_url     = excluded.github_url,
            demo_url       = excluded.demo_url,
            last_scan_at   = excluded.last_scan_at
        """,
        (
            url,
            details.get("project_name") or listing.get("project_name") or "Untitled",
            details.get("tagline") or listing.get("tagline"),
            details.get("hackathon_name"),
            details.get("prize"),
            details.get("team"),
            details.get("github_url"),
            details.get("demo_url"),
            details["submitted_at"].isoformat() if details.get("submitted_at") else None,
            now_iso,
            now_iso,
        ),
    )
    db.commit()
