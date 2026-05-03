from __future__ import annotations

import base64
from dataclasses import dataclass, field

from src.scanner.github_client import GithubClient


@dataclass
class RepoContext:
    readme: str | None
    recent_commits: list[str]
    top_issues: list[str]
    description: str | None
    topics: list[str]
    language: str | None


def fetch_repo_context(full_name: str, client: GithubClient) -> RepoContext:
    readme: str | None = None
    try:
        data = client._request("GET", f"/repos/{full_name}/readme").json()
        raw = data.get("content", "")
        readme = base64.b64decode(raw.replace("\n", "")).decode("utf-8", errors="replace")
    except Exception:
        readme = None

    commits: list[str] = []
    try:
        items = client._request("GET", f"/repos/{full_name}/commits", params={"per_page": 10}).json()
        commits = [c["commit"]["message"].split("\n")[0] for c in items if isinstance(c, dict)]
    except Exception:
        pass

    issues: list[str] = []
    try:
        items = client._request(
            "GET", f"/repos/{full_name}/issues",
            params={"state": "open", "per_page": 10, "sort": "reactions"},
        ).json()
        issues = [i["title"] for i in items if isinstance(i, dict)]
    except Exception:
        pass

    repo_data: dict = {}
    try:
        repo_data = client.get_repo(full_name)
    except Exception:
        pass

    return RepoContext(
        readme=readme,
        recent_commits=commits,
        top_issues=issues,
        description=repo_data.get("description"),
        topics=repo_data.get("topics", []),
        language=repo_data.get("language"),
    )
