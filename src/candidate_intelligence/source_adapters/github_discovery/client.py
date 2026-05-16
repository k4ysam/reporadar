from __future__ import annotations

import time
from datetime import datetime

import psycopg
import requests

from src.common.db import log_api_call


class GithubClient:
    BASE = "https://api.github.com"

    def __init__(self, conn: psycopg.Connection, run_id: str, token: str):
        self._conn = conn
        self._run_id = run_id
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
        )

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = f"{self.BASE}{path}"
        max_retries = 3
        delay = 1.0
        for attempt in range(max_retries):
            t0 = time.monotonic()
            resp = self._session.request(method, url, **kwargs)
            latency_ms = int((time.monotonic() - t0) * 1000)
            log_api_call(self._conn, self._run_id, "github", path, resp.status_code, latency_ms)

            if resp.status_code in (429, 403):
                retry_after = int(resp.headers.get("Retry-After", delay))
                if attempt < max_retries - 1:
                    time.sleep(retry_after)
                    delay *= 2
                    continue
            resp.raise_for_status()
            return resp
        resp.raise_for_status()
        return resp

    def get_rate_limit(self) -> dict:
        return self._request("GET", "/rate_limit").json()

    def search_repos(self, query: str, sort: str = "stars", per_page: int = 50) -> list[dict]:
        resp = self._request(
            "GET",
            "/search/repositories",
            params={"q": query, "sort": sort, "per_page": per_page},
        )
        return resp.json().get("items", [])

    def get_repo(self, full_name: str) -> dict:
        return self._request("GET", f"/repos/{full_name}").json()

    def get_stargazers_with_timestamps(
        self, full_name: str, since: datetime, max_pages: int = 5
    ) -> list[datetime]:
        timestamps: list[datetime] = []
        headers = {"Accept": "application/vnd.github.star+json"}
        for page in range(1, max_pages + 1):
            url = f"{self.BASE}/repos/{full_name}/stargazers"
            t0 = time.monotonic()
            resp = self._session.get(
                url, headers=headers, params={"per_page": 100, "page": page}
            )
            latency_ms = int((time.monotonic() - t0) * 1000)
            log_api_call(
                self._conn,
                self._run_id,
                "github",
                f"/repos/{full_name}/stargazers",
                resp.status_code,
                latency_ms,
            )
            if not resp.ok or not resp.json():
                break
            for entry in resp.json():
                starred_at = datetime.fromisoformat(entry["starred_at"].replace("Z", "+00:00"))
                if starred_at < since:
                    return timestamps
                timestamps.append(starred_at)
        return timestamps
