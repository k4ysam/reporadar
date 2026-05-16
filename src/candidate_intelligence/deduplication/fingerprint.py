"""Canonical-key derivation for cross-source deduplication.

A "canonical_repo_key" is the universal identity used in both
`candidate_repository_evaluations.canonical_repo_key` and
`posted_repositories.canonical_repo_key`. Format:

    github:<owner>/<repo>      from GitHub URLs
    devpost:<slug>             from Devpost URLs

Future sources (Product Hunt, HN, Reddit, etc.) should follow the same
`<source>:<id>` pattern so the same project can be matched across them.
"""
from __future__ import annotations

from urllib.parse import urlparse


def canonical_key_for_github(url_or_full_name: str) -> str:
    if url_or_full_name.startswith("http"):
        parts = urlparse(url_or_full_name).path.strip("/").split("/")
        if len(parts) < 2:
            raise ValueError(f"GitHub URL must contain owner/repo: {url_or_full_name!r}")
        full_name = f"{parts[0]}/{parts[1]}"
    else:
        full_name = url_or_full_name.strip("/")
    return f"github:{full_name}"


def canonical_key_for_devpost(devpost_url: str) -> str:
    slug = devpost_url.rstrip("/").split("/")[-1]
    return f"devpost:{slug}"
