from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from src.config import Settings

_log = logging.getLogger(__name__)
GRAPH_BASE = "https://graph.facebook.com/v20.0"


def get_token_debug(access_token: str, app_id: str, app_secret: str) -> dict[str, Any]:
    app_token = f"{app_id}|{app_secret}"
    resp = requests.get(
        f"{GRAPH_BASE}/debug_token",
        params={"input_token": access_token, "access_token": app_token},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("data", {})


def days_until_expiry(access_token: str, app_id: str, app_secret: str) -> int | None:
    try:
        info = get_token_debug(access_token, app_id, app_secret)
    except Exception as exc:
        _log.warning("Could not debug token: %s", exc)
        return None
    expires_at = info.get("expires_at") or info.get("data_access_expires_at")
    if not expires_at:
        return None
    expiry = datetime.fromtimestamp(int(expires_at), tz=timezone.utc)
    delta = expiry - datetime.now(timezone.utc)
    return max(delta.days, 0)


def refresh_long_lived_token(short_token: str, app_id: str, app_secret: str) -> str:
    """Exchange a short-lived token for a long-lived (≈60 day) one."""
    resp = requests.get(
        f"{GRAPH_BASE}/oauth/access_token",
        params={
            "grant_type": "fb_exchange_token",
            "client_id": app_id,
            "client_secret": app_secret,
            "fb_exchange_token": short_token,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def check_and_alert(settings: Settings, *, alert_threshold_days: int = 14) -> dict[str, Any]:
    """Return a status dict; log a warning if expiry within threshold.

    Caller can wire this into any alerting channel (logs, email, webhook).
    """
    if not all((settings.ig_access_token, settings.ig_app_id, settings.ig_app_secret)):
        return {"status": "skipped", "reason": "missing IG_APP_ID / IG_APP_SECRET / IG_ACCESS_TOKEN"}
    days_left = days_until_expiry(
        settings.ig_access_token, settings.ig_app_id, settings.ig_app_secret
    )
    if days_left is None:
        return {"status": "unknown"}
    if days_left <= alert_threshold_days:
        _log.warning("Instagram access token expires in %d days — refresh soon!", days_left)
        return {"status": "expiring_soon", "days_left": days_left}
    return {"status": "ok", "days_left": days_left}
