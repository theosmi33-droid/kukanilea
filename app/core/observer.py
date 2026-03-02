from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger("kukanilea.core.observer")

try:
    import psutil  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    psutil = None


def get_system_status() -> Dict[str, Any]:
    """
    Returns current system health metrics.
    Works even when psutil is unavailable (e.g. CI minimal env).
    """
    if psutil is None:
        return {
            "status": "DEGRADED_NO_PSUTIL",
            "cpu_usage_pct": None,
            "memory_rss_mb": None,
            "observer_active": True,
            "validation_gate": "ENFORCED",
            "db_locked": False,
        }

    try:
        process = psutil.Process()
        memory_info = process.memory_info()
        cpu_usage = psutil.cpu_percent(interval=0.1)

        status = "HEALTHY"
        if memory_info.rss > 512 * 1024 * 1024:
            status = "WARNING_MEMORY"
            logger.warning("System Memory High: %.2f MB", memory_info.rss / (1024 * 1024))

        return {
            "status": status,
            "cpu_usage_pct": cpu_usage,
            "memory_rss_mb": memory_info.rss / (1024 * 1024),
            "observer_active": True,
            "validation_gate": "ENFORCED",
            "db_locked": False,
        }
    except Exception as exc:
        logger.error("Observer failed to collect system status: %s", exc)
        return {
            "status": "ERROR",
            "error": str(exc),
            "observer_active": True,
        }
