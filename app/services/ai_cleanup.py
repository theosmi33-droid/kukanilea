"""Cleanup low-importance AI memory entries older than retention."""

from __future__ import annotations

import logging
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger("ai_cleanup")

MEMORY_ROOT = os.environ.get("KUKANILEA_AI_MEMORY_ROOT", "instance/ai_memory")
DEFAULT_AUTH_DB = os.environ.get("KUKANILEA_AUTH_DB", "instance/auth.sqlite3")
KNOWLEDGE_MEMORY_RETENTION_DAYS = int(os.environ.get("KUKANILEA_MEMORY_RETENTION_DAYS", "60"))


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


def cleanup_auth_memory(db_path: str = DEFAULT_AUTH_DB, days: int = 60) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    conn = sqlite3.connect(db_path)
    try:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(agent_memory)").fetchall()}
        cutoff_iso = cutoff.isoformat()
        if "timestamp" in columns and "category" in columns:
            conn.execute(
                "DELETE FROM agent_memory WHERE timestamp < ? AND category = 'KNOWLEDGE_MEMORY'",
                (cutoff_iso,),
            )
        elif "created_at" in columns:
            conn.execute("DELETE FROM agent_memory WHERE created_at < ?", (cutoff_iso,))
        elif "timestamp" in columns:
            conn.execute("DELETE FROM agent_memory WHERE timestamp < ?", (cutoff_iso,))
        else:
            return 0
        deleted = conn.total_changes
        conn.commit()
        logger.info("Cleanup auth memory %s -> deleted %d rows", db_path, deleted)
        return deleted
    finally:
        conn.close()


def run_nightly_cleanup(days: int | None = None) -> None:
    """Entry-point for nightly retention job."""

    cleanup_all_tenants()
    retention_days = int(days if days is not None else KNOWLEDGE_MEMORY_RETENTION_DAYS)
    try:
        cleanup_auth_memory(days=retention_days)
    except Exception:
        logger.exception("Cleanup failed for auth memory")


if __name__ == "__main__":
    run_nightly_cleanup()
