"""Production WSGI entrypoint for Render (and any container host).

A single process runs both the Flask dashboard and the APScheduler daily
pipeline. The scheduler is in-process (BackgroundScheduler) so it shares
the OUTPUT_DIR volume with the dashboard — the daemon writes rendered
post images, the dashboard serves them.

Run with:
    gunicorn -w 1 -k gthread --threads 8 --timeout 180 \
        -b 0.0.0.0:$PORT src.operator_api.web.wsgi:app

`-w 1` is REQUIRED. BackgroundScheduler lives inside the gunicorn worker
process; with -w >1 the cron job would fire once per worker.

Local dev still uses `python -m src serve` and `python -m src daemon`
separately — this module is only the production codepath.
"""
from __future__ import annotations

import atexit
import logging
import random
import time

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from src.common.config import Settings
from src.common.db import connect
from src.operator_api.web.app import create_app
from src.orchestrator.pipeline import run_pipeline
from src.scheduler.daemon import _cron_offset

_log = logging.getLogger(__name__)

settings = Settings.from_env()
app = create_app(settings)


def _content_job() -> None:
    delay_minutes = random.randint(0, 2 * settings.schedule_jitter_minutes)
    if delay_minutes:
        _log.info("Jitter sleep: %d min before pipeline run", delay_minutes)
        time.sleep(delay_minutes * 60)
    with connect(settings) as conn:
        try:
            run_pipeline(conn, settings, requested_by="scheduler")
        except Exception as exc:
            _log.exception("Pipeline run raised: %s", exc)


_scheduler = BackgroundScheduler(timezone=settings.timezone_name)
_cron_hour, _cron_minute = _cron_offset(
    settings.schedule_hour, settings.schedule_jitter_minutes
)
_scheduler.add_job(
    _content_job,
    CronTrigger(
        hour=_cron_hour, minute=_cron_minute, timezone=settings.timezone_name
    ),
    id="content",
    name="Daily content pipeline",
    max_instances=1,
    coalesce=True,
)
_scheduler.start()
atexit.register(lambda: _scheduler.shutdown(wait=False))
_log.info(
    "In-process scheduler started: daily content at %02d:00 %s ±%d min",
    settings.schedule_hour,
    settings.timezone_name,
    settings.schedule_jitter_minutes,
)
