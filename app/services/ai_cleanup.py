"""Cleanup low-importance AI memory entries older than retention."""

from __future__ import annotations

import logging
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger("ai_cleanup")

MEMORY_ROOT = os.environ.get("KUKANILEA_AI_MEMORY_ROOT", "instance/ai_memory")


def cleanup_tenant_db(db_path: str, days: int = 60, min_importance: int = 8) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "DELETE FROM messages WHERE created_at < ? AND (importance_score IS NULL OR importance_score < ?)",
            (cutoff.isoformat(), min_importance),
        )
        deleted = conn.total_changes
        conn.commit()
        conn.execute("VACUUM")
        logger.info("Cleanup %s -> deleted %d messages", db_path, deleted)
        return deleted
    finally:
        conn.close()


def cleanup_all_tenants() -> None:
    root = Path(MEMORY_ROOT)
    root.mkdir(parents=True, exist_ok=True)

    for db_file in root.glob("*.db"):
        try:
            cleanup_tenant_db(str(db_file))
        except Exception:
            logger.exception("Cleanup failed for %s", db_file)


if __name__ == "__main__":
    cleanup_all_tenants()
