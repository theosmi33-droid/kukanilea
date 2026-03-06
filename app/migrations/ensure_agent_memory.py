"""Idempotent ensure script for agent_memory, memory_audit_log and api_outbound_queue tables."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

DEFAULT_DB = os.environ.get("KUKANILEA_AUTH_DB", "instance/auth.sqlite3")


def ensure_agent_memory_tables(db_path: str = DEFAULT_DB) -> None:
    db_parent = Path(db_path).parent
    db_parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_memory (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                agent_name TEXT,
                content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_agent_memory_tenant ON agent_memory(tenant_id);"
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_audit_log (
                id TEXT PRIMARY KEY,
                memory_id TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                action TEXT NOT NULL,
                actor TEXT NOT NULL,
                payload TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_memory_audit_tenant_ts ON memory_audit_log(tenant_id, created_at);"
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS api_outbound_queue (
                id TEXT PRIMARY KEY,
                tenant_id TEXT,
                payload TEXT,
                status TEXT DEFAULT 'pending',
                attempts INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_attempt TIMESTAMP NULL
            );
            """
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_outbound_tenant_status ON api_outbound_queue(tenant_id, status);"
        )

        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    ensure_agent_memory_tables()
    print(f"Ensured agent_memory, memory_audit_log and api_outbound_queue in {DEFAULT_DB}")
