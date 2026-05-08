from __future__ import annotations

import logging
import sqlite3
import time
from typing import Iterable

import requests

from src.db import log_api_call

_log = logging.getLogger(__name__)
GRAPH_BASE = "https://graph.facebook.com/v20.0"


class InstagramError(RuntimeError):
    pass


class InstagramClient:
    def __init__(
        self,
        db: sqlite3.Connection,
        run_id: str,
        access_token: str,
        ig_user_id: str,
        session: requests.Session | None = None,
    ):
        if not access_token or not ig_user_id:
            raise RuntimeError("InstagramClient requires access_token and ig_user_id")
        self._db = db
        self._run_id = run_id
        self._token = access_token
        self._user_id = ig_user_id
        self._session = session or requests.Session()

    def _request(self, method: str, path: str, params: dict | None = None, data: dict | None = None) -> dict:
        url = f"{GRAPH_BASE}{path}"
        params = dict(params or {})
        params.setdefault("access_token", self._token)
        t0 = time.monotonic()
        resp = self._session.request(method, url, params=params, data=data, timeout=60)
        latency_ms = int((time.monotonic() - t0) * 1000)
        log_api_call(self._db, self._run_id, "instagram", path, resp.status_code, latency_ms)
        if not resp.ok:
            raise InstagramError(f"{method} {path} → {resp.status_code}: {resp.text[:300]}")
        return resp.json()

    # --- single image ---
    def create_image_container(self, image_url: str, caption: str) -> str:
        body = self._request(
            "POST",
            f"/{self._user_id}/media",
            data={"image_url": image_url, "caption": caption},
        )
        return body["id"]

    # --- carousel ---
    def create_child_container(self, image_url: str) -> str:
        body = self._request(
            "POST",
            f"/{self._user_id}/media",
            data={"image_url": image_url, "is_carousel_item": "true"},
        )
        return body["id"]

    def create_carousel_container(self, child_ids: Iterable[str], caption: str) -> str:
        body = self._request(
            "POST",
            f"/{self._user_id}/media",
            data={
                "media_type": "CAROUSEL",
                "children": ",".join(child_ids),
                "caption": caption,
            },
        )
        return body["id"]

    # --- publish ---
    def wait_for_finished(self, container_id: str, *, timeout_seconds: int = 120) -> None:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            body = self._request(
                "GET",
                f"/{container_id}",
                params={"fields": "status_code,status"},
            )
            status = body.get("status_code") or body.get("status")
            if status == "FINISHED":
                return
            if status in ("ERROR", "EXPIRED"):
                raise InstagramError(f"Container {container_id} failed: {body}")
            time.sleep(3)
        raise InstagramError(f"Container {container_id} did not finish within {timeout_seconds}s")

    def publish(self, container_id: str) -> dict:
        return self._request(
            "POST",
            f"/{self._user_id}/media_publish",
            data={"creation_id": container_id},
        )

    def get_permalink(self, media_id: str) -> str | None:
        try:
            body = self._request("GET", f"/{media_id}", params={"fields": "permalink"})
            return body.get("permalink")
        except InstagramError:
            return None

    # --- high level flows ---
    def post_single(self, image_url: str, caption: str) -> dict:
        container = self.create_image_container(image_url, caption)
        self.wait_for_finished(container)
        published = self.publish(container)
        media_id = published["id"]
        return {"media_id": media_id, "permalink": self.get_permalink(media_id)}

    def post_carousel(self, image_urls: list[str], caption: str) -> dict:
        if not 2 <= len(image_urls) <= 10:
            raise InstagramError("Carousel must have 2–10 items")
        children = [self.create_child_container(url) for url in image_urls]
        for c in children:
            self.wait_for_finished(c)
        carousel = self.create_carousel_container(children, caption)
        self.wait_for_finished(carousel)
        published = self.publish(carousel)
        media_id = published["id"]
        return {"media_id": media_id, "permalink": self.get_permalink(media_id)}
