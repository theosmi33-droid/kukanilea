from __future__ import annotations

import os
from typing import Optional

from flask import Flask

from .knowledge import init_chroma
from .predictions import daily_report

_SCHEDULER = None


def init_ai(app: Optional[Flask] = None) -> None:
    """Initialize local AI services (knowledge base + optional scheduler)."""
    init_chroma()

    # Default OFF in tests and unless explicitly enabled.
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

    scheduler = BackgroundScheduler(timezone="UTC")

    def _run_daily() -> None:
        with app.app_context():
            daily_report()

    scheduler.add_job(_run_daily, "cron", hour=6, minute=30, id="ai_daily_report")
    scheduler.start()
    _SCHEDULER = scheduler
