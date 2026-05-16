"""Fetch README + recent commits + top issues for a GitHub candidate."""
from __future__ import annotations

import base64

from src.candidate_intelligence.source_adapters.github_discovery.client import GithubClient
from src.contracts.candidate import RepoEnrichment


def enrich_github_candidate(full_name: str, client: GithubClient) -> RepoEnrichment:
    readme: str | None = None
    try:
        data = client._request("GET", f"/repos/{full_name}/readme").json()
        raw = data.get("content", "")
        readme = base64.b64decode(raw.replace("\n", "")).decode("utf-8", errors="replace")
    except Exception:
        readme = None

    commits: list[str] = []
    try:
        items = client._request(
            "GET", f"/repos/{full_name}/commits", params={"per_page": 10}
        ).json()
        commits = [c["commit"]["message"].split("\n")[0] for c in items if isinstance(c, dict)]
    except Exception:
        pass

    issues: list[str] = []
    try:
        items = client._request(
            "GET",
            f"/repos/{full_name}/issues",
            params={"state": "open", "per_page": 10, "sort": "reactions"},
        ).json()
        issues = [i["title"] for i in items if isinstance(i, dict)]
    except Exception:
        pass

    readme_lower = (readme or "").lower()
    return RepoEnrichment(
        readme=readme,
        recent_commits=commits,
        top_issues=issues,
        has_installation_instructions="install" in readme_lower or "getting started" in readme_lower,
        has_usage_examples="usage" in readme_lower or "example" in readme_lower,
    )
