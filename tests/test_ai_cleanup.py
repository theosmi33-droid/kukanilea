from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from app.services.ai_cleanup import cleanup_auth_memory


def test_cleanup_auth_memory_deletes_entries_older_than_60_days(tmp_path):
    db_path = tmp_path / "auth.sqlite3"
    con = sqlite3.connect(db_path)
    try:
        con.execute(
            "CREATE TABLE agent_memory (id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, agent_name TEXT, content TEXT, timestamp TEXT)"
        )
        now = datetime.now(timezone.utc)
        old = (now - timedelta(days=61)).isoformat()
        fresh = (now - timedelta(days=5)).isoformat()
        con.execute(
            "INSERT INTO agent_memory(id, tenant_id, agent_name, content, timestamp) VALUES (?,?,?,?,?)",
            ("old", "T1", "ai-runtime", "{}", old),
        )
        con.execute(
            "INSERT INTO agent_memory(id, tenant_id, agent_name, content, timestamp) VALUES (?,?,?,?,?)",
            ("fresh", "T2", "ai-runtime", "{}", fresh),
        )
        con.commit()
    finally:
        con.close()

    deleted = cleanup_auth_memory(str(db_path), days=60)
    assert deleted == 1

    con = sqlite3.connect(db_path)
    try:
        rows = con.execute("SELECT id FROM agent_memory ORDER BY id").fetchall()
    finally:
        con.close()
    assert rows == [("fresh",)]
