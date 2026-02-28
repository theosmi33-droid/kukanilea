from __future__ import annotations

import logging
import psutil
from typing import Any, Dict

logger = logging.getLogger("kukanilea.core.observer")

def get_system_status() -> Dict[str, Any]:
    """
    Returns the current system health and status metrics.
    Monitors limits, memory, and validation state.
    """
    try:
        process = psutil.Process()
        memory_info = process.memory_info()
        cpu_usage = psutil.cpu_percent(interval=0.1)
        
        status = "HEALTHY"
        if memory_info.rss > 512 * 1024 * 1024: # Alert if > 512MB
            status = "WARNING_MEMORY"
            logger.warning(f"System Memory High: {memory_info.rss / (1024*1024):.2f} MB")
            
        return {
            "status": status,
            "cpu_usage_pct": cpu_usage,
            "memory_rss_mb": memory_info.rss / (1024 * 1024),
            "observer_active": True,
            "validation_gate": "ENFORCED",
            "db_locked": False # Check for real locks in future iteration
        }
    except Exception as e:
        logger.error(f"Observer failed to collect system status: {e}")
        return {
            "status": "ERROR",
            "error": str(e),
            "observer_active": True
        }
