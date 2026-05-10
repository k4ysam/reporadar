"""APScheduler daemon. Daily fire at SCHEDULE_HOUR ±SCHEDULE_JITTER_MINUTES.

Generates the top post across all content types and saves it locally for human review.
"""
from __future__ import annotations

import logging
import random
import signal
import time

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from src.config import Settings
from src.db import get_db, init_db
from src.pipeline import run_pipeline

_log = logging.getLogger(__name__)


def _cron_offset(schedule_hour: int, jitter_minutes: int) -> tuple[int, int]:
    """Return (cron_hour, cron_minute) shifted `jitter_minutes` before SCHEDULE_HOUR.

    Cron fires `jitter` minutes early; the job then sleeps a random [0, 2*jitter]
    minutes, yielding an effective post time uniformly in [hour-jitter, hour+jitter].
    """
    total = schedule_hour * 60 - jitter_minutes
    return (total // 60) % 24, total % 60


def _content_job(settings: Settings) -> None:
    delay_minutes = random.randint(0, 2 * settings.schedule_jitter_minutes)
    if delay_minutes:
        _log.info("Jitter sleep: %d min before generating post", delay_minutes)
        time.sleep(delay_minutes * 60)

    db = get_db(settings.db_path)
    try:
        run_pipeline(db, settings)
    except Exception as exc:
        _log.exception("Pipeline run raised: %s", exc)
    finally:
        db.close()


def build_scheduler(settings: Settings) -> BlockingScheduler:
    sched = BlockingScheduler(timezone=settings.timezone_name)
    cron_hour, cron_minute = _cron_offset(
        settings.schedule_hour, settings.schedule_jitter_minutes
    )
    sched.add_job(
        _content_job,
        CronTrigger(hour=cron_hour, minute=cron_minute, timezone=settings.timezone_name),
        args=[settings],
        id="content",
        name="Daily content pipeline",
        max_instances=1,
        coalesce=True,
    )
    return sched


def run_forever(settings: Settings) -> None:
    init_db(settings.db_path)
    sched = build_scheduler(settings)

    def _shutdown(signum, frame):
        _log.info("Received signal %d, shutting down scheduler", signum)
        sched.shutdown(wait=False)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    _log.info(
        "Scheduler started: daily content at %02d:00 %s ±%d min",
        settings.schedule_hour,
        settings.timezone_name,
        settings.schedule_jitter_minutes,
    )
    sched.start()
