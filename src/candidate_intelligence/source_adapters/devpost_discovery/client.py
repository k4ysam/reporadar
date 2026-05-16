from __future__ import annotations

import time
from datetime import datetime
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

import psycopg
import requests
from bs4 import BeautifulSoup

from src.common.db import log_api_call

USER_AGENT = "RepoRadarBot/1.0 (+https://github.com/reporadar; respects robots.txt)"
DEVPOST_BASE = "https://devpost.com"
DEFAULT_RATE_LIMIT_SECONDS = 1.5


class DevpostClient:
    def __init__(
        self,
        conn: psycopg.Connection,
        run_id: str,
        rate_limit_seconds: float = DEFAULT_RATE_LIMIT_SECONDS,
        session: requests.Session | None = None,
    ):
        self._conn = conn
        self._run_id = run_id
        self._rate = rate_limit_seconds
        self._last_request_at: float = 0.0
        self._session = session or requests.Session()
        self._session.headers.update({"User-Agent": USER_AGENT})
        self._robots: RobotFileParser | None = None

    def _load_robots(self) -> RobotFileParser:
        if self._robots is None:
            rp = RobotFileParser()
            rp.set_url(f"{DEVPOST_BASE}/robots.txt")
            try:
                rp.read()
            except Exception:
                pass
            self._robots = rp
        return self._robots

    def _can_fetch(self, url: str) -> bool:
        rp = self._load_robots()
        try:
            return rp.can_fetch(USER_AGENT, url)
        except Exception:
            return True

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self._rate:
            time.sleep(self._rate - elapsed)
        self._last_request_at = time.monotonic()

    def get(self, url: str) -> requests.Response | None:
        if not self._can_fetch(url):
            return None
        self._throttle()
        t0 = time.monotonic()
        resp = self._session.get(url, timeout=30)
        latency_ms = int((time.monotonic() - t0) * 1000)
        log_api_call(self._conn, self._run_id, "devpost", url, resp.status_code, latency_ms)
        return resp

    def list_recent_software(self, limit: int = 25, sort: str = "recently-added") -> list[dict]:
        url = f"{DEVPOST_BASE}/software/search?sort_by={sort}"
        resp = self.get(url)
        if resp is None or not resp.ok:
            return []
        return _parse_software_listing(resp.text, limit=limit)

    def fetch_project(self, project_url: str) -> dict | None:
        full_url = project_url if project_url.startswith("http") else urljoin(DEVPOST_BASE, project_url)
        resp = self.get(full_url)
        if resp is None or not resp.ok:
            return None
        data = _parse_project_page(resp.text)
        data["devpost_url"] = full_url
        return data


def _parse_software_listing(html: str, limit: int) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    out: list[dict] = []
    for el in soup.select("a.block-wrapper-link, a.software-entry-link, a[data-software-id]"):
        href = el.get("href")
        if not href:
            continue
        if not href.startswith("http"):
            href = urljoin(DEVPOST_BASE, href)
        title_el = el.select_one("h5, .software-title, .name")
        tagline_el = el.select_one(".tagline, .small-tagline, p.tagline")
        out.append(
            {
                "devpost_url": href,
                "project_name": (
                    title_el.get_text(strip=True) if title_el else el.get_text(strip=True)
                )[:200],
                "tagline": tagline_el.get_text(strip=True) if tagline_el else None,
            }
        )
        if len(out) >= limit:
            break
    seen: set[str] = set()
    deduped: list[dict] = []
    for item in out:
        if item["devpost_url"] in seen:
            continue
        seen.add(item["devpost_url"])
        deduped.append(item)
    return deduped


def _parse_project_page(html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")

    title_el = soup.select_one("#app-title, h1#app-title, h1")
    title = title_el.get_text(strip=True) if title_el else ""

    tagline_el = soup.select_one("p.large, .software-tagline, header p")
    tagline = tagline_el.get_text(strip=True) if tagline_el else None

    github_url: str | None = None
    for a in soup.select("a[href*='github.com']"):
        href = a.get("href", "")
        if "github.com" in href and "/login" not in href:
            github_url = href.split("?")[0]
            break

    demo_url: str | None = None
    for a in soup.select("a.app-links, ul.no-bullet a, .software-urls a"):
        href = a.get("href", "")
        if href.startswith("http") and "github.com" not in href and "devpost.com" not in href:
            demo_url = href
            break

    hackathon_name: str | None = None
    h_el = soup.select_one(".software-list-content a[href*='/hackathons'], a[href*='.devpost.com']")
    if h_el:
        hackathon_name = h_el.get_text(strip=True) or None

    prize: str | None = None
    prize_el = soup.select_one("#submissions, .winner, .prize")
    if prize_el:
        prize = prize_el.get_text(" ", strip=True)[:200]
    if not prize:
        for el in soup.select("li, p"):
            text = el.get_text(" ", strip=True)
            if text.lower().startswith("winner") or "🏆" in text:
                prize = text[:200]
                break

    team_members: list[str] = []
    for el in soup.select("ul.software-team-members li, .software-team-members .user-profile-link"):
        name = el.get_text(strip=True)
        if name:
            team_members.append(name)
    team = ", ".join(team_members[:6]) or None

    technologies: list[str] = []
    for el in soup.select("#built-with li, .cp-tag, .technology-tag"):
        tech = el.get_text(strip=True)
        if tech:
            technologies.append(tech)

    desc_parts: list[str] = []
    for h in soup.select("h2, h3"):
        heading = h.get_text(strip=True).lower()
        if heading in ("what it does", "inspiration"):
            sib = h.find_next_sibling()
            if sib:
                desc_parts.append(sib.get_text(" ", strip=True))
    description = "\n\n".join(desc_parts)[:4000] or None

    submitted_at: datetime | None = None
    time_el = soup.select_one("time[datetime]")
    if time_el and time_el.get("datetime"):
        try:
            submitted_at = datetime.fromisoformat(time_el["datetime"].replace("Z", "+00:00"))
        except Exception:
            submitted_at = None

    return {
        "project_name": title,
        "tagline": tagline,
        "github_url": github_url,
        "demo_url": demo_url,
        "hackathon_name": hackathon_name,
        "prize": prize,
        "team": team,
        "technologies": technologies[:20],
        "description": description,
        "submitted_at": submitted_at,
    }
