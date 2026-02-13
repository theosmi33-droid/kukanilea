from __future__ import annotations

import os
from typing import Optional

from flask import Flask

_SCHEDULER = None
_TRUTHY = {"1", "true", "yes", "on"}


def is_enabled() -> bool:
    return str(os.environ.get("KUKA_AI_ENABLE", "")).strip().lower() in _TRUTHY


def init_ai(app: Optional[Flask] = None) -> None:
    """Initialize local AI services (knowledge base + optional scheduler).

    Heavy optional AI dependencies are only touched when KUKA_AI_ENABLE is truthy.
    """
    if not is_enabled():
        return

    from .knowledge import init_chroma

    init_chroma()

    if app is None:
        return
    if app.config.get("TESTING"):
        return
    if os.environ.get("KUKANILEA_AI_SCHEDULER", "0") != "1":
        return

    global _SCHEDULER
    if _SCHEDULER is not None:
        return

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except Exception:
        return

    from .predictions import daily_report

    scheduler = BackgroundScheduler(timezone="UTC")

    def _run_daily() -> None:
        with app.app_context():
            daily_report()

    scheduler.add_job(_run_daily, "cron", hour=6, minute=30, id="ai_daily_report")
    scheduler.start()
    _SCHEDULER = scheduler
