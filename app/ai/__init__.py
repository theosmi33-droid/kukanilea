from __future__ import annotations

import importlib.util
import os

from flask import Flask

from .memory import ensure_ai_schema
from .personal_memory import ensure_personal_memory_schema

_SCHEDULER = None
_TRUTHY = {"1", "true", "yes", "on"}
_REQUIRED_AI_PACKAGES = ("chromadb", "sentence_transformers", "ollama")


def is_enabled() -> bool:
    return str(os.environ.get("KUKA_AI_ENABLE", "")).strip().lower() in _TRUTHY


def missing_ai_dependencies() -> list[str]:
    missing: list[str] = []
    for pkg in _REQUIRED_AI_PACKAGES:
        if importlib.util.find_spec(pkg) is None:
            missing.append(pkg)
    return missing


def ensure_ai_dependencies() -> None:
    missing = missing_ai_dependencies()
    if not missing:
        return
    hint = "pip install chromadb sentence-transformers ollama"
    raise RuntimeError(
        "AI is enabled (KUKA_AI_ENABLE=1) but missing optional dependencies: "
        f"{', '.join(missing)}. Install with: {hint}"
    )


def init_ai(app: Flask | None = None) -> None:
    """Initialize local AI services (knowledge base + optional scheduler).

    Heavy optional AI dependencies are only touched when KUKA_AI_ENABLE is truthy.
    """
    ensure_ai_schema()
    ensure_personal_memory_schema()
    if not is_enabled():
        return

    ensure_ai_dependencies()

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
