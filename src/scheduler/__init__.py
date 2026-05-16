"""Scheduler service. Owns cron-like behavior; emits RunRequested by calling
the orchestrator. Does not know how discovery, evaluation, or rendering work.
"""
from src.scheduler.daemon import build_scheduler, run_forever

__all__ = ["build_scheduler", "run_forever"]
