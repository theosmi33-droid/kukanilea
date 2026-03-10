from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.agents.memory_store import MemoryManager


def _setup_db(path: str) -> None:
    con = sqlite3.connect(path)
    try:
        con.execute(
            """
            CREATE TABLE agent_memory(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              tenant_id TEXT NOT NULL,
              timestamp TEXT NOT NULL,
              agent_role TEXT NOT NULL,
              content TEXT NOT NULL,
              embedding BLOB NOT NULL,
              metadata TEXT,
              importance_score INTEGER DEFAULT 5,
              category TEXT DEFAULT 'FAKT'
            );
            """
        )
        con.execute(
            """
            CREATE TABLE memory_audit_log(
              id TEXT PRIMARY KEY,
              memory_id TEXT NOT NULL,
              tenant_id TEXT NOT NULL,
              action TEXT NOT NULL,
              actor TEXT NOT NULL,
              payload TEXT,
              created_at TEXT NOT NULL
            );
            """
        )
        con.commit()
    finally:
        con.close()


def test_knowledge_memory_write_requires_confirm(tmp_path):
    db_path = tmp_path / "auth.sqlite3"
    _setup_db(str(db_path))
    manager = MemoryManager(str(db_path))

    response = manager.store_knowledge_memory(
        tenant_id="TENANT_A",
        content="Bevorzugte Zahlungsart ist Lastschrift",
        topic="finance",
        memory_type="preference",
        actor="agent",
        confirm_write=False,
    )
    assert response["status"] == "pending_confirmation"

    con = sqlite3.connect(db_path)
    try:
        rows = con.execute("SELECT COUNT(*) FROM agent_memory").fetchone()[0]
    finally:
        con.close()
    assert rows == 0


def test_knowledge_memory_topic_retrieval_and_tenant_isolation(tmp_path):
    db_path = tmp_path / "auth.sqlite3"
    _setup_db(str(db_path))

    with patch("app.agents.memory_store.generate_embedding", return_value=[1.0, 0.0, 0.0]):
        manager = MemoryManager(str(db_path))
        now = datetime.now(timezone.utc)
        fresh = (now - timedelta(days=2)).isoformat() + "Z"
        stale = (now - timedelta(days=20)).isoformat() + "Z"

        manager.store_knowledge_memory(
            tenant_id="TENANT_A",
            content="Kontakt ist im CRM unter C-1042 referenziert",
            topic="contacts",
            memory_type="contact_reference",
            actor="agent",
            confirm_write=True,
        )
        manager.store_knowledge_memory(
            tenant_id="TENANT_B",
            content="B-only note",
            topic="contacts",
            memory_type="note",
            actor="agent",
            confirm_write=True,
        )

    con = sqlite3.connect(db_path)
    try:
        memory_id = con.execute("SELECT id FROM agent_memory WHERE tenant_id='TENANT_A' ORDER BY id DESC LIMIT 1").fetchone()[0]
        con.execute("UPDATE agent_memory SET timestamp=? WHERE id=?", (fresh, memory_id))
        con.execute(
            "INSERT INTO agent_memory(tenant_id, timestamp, agent_role, content, embedding, metadata, importance_score, category) VALUES (?,?,?,?,?,?,?,?)",
            (
                "TENANT_A",
                stale,
                "agent",
                "Älterer Kontakt-Hinweis",
                sqlite3.Binary(b"\x00\x00\x80?"),
                '{"topic":"contacts","memory_type":"contact_reference"}',
                6,
                "KNOWLEDGE_MEMORY",
            ),
        )
        con.commit()
    finally:
        con.close()

    manager = MemoryManager(str(db_path))
    hits = manager.retrieve_by_topic(tenant_id="TENANT_A", topic="contacts", limit=2, recency_days=60)
    assert len(hits) == 2
    assert "CRM" in hits[0]["content"]
    assert all("B-only" not in item["content"] for item in hits)
    assert hits[0]["score"] > hits[1]["score"]


def test_knowledge_memory_cleanup_writes_delete_audit(tmp_path):
    db_path = tmp_path / "auth.sqlite3"
    _setup_db(str(db_path))
    manager = MemoryManager(str(db_path))

    now = datetime.now(timezone.utc)
    old = (now - timedelta(days=70)).isoformat() + "Z"
    fresh = (now - timedelta(days=1)).isoformat() + "Z"

    con = sqlite3.connect(db_path)
    try:
        con.execute(
            "INSERT INTO agent_memory(tenant_id, timestamp, agent_role, content, embedding, metadata, importance_score, category) VALUES (?,?,?,?,?,?,?,?)",
            ("TENANT_A", old, "agent", "Old km", sqlite3.Binary(b"\x00\x00\x80?"), "{}", 5, "KNOWLEDGE_MEMORY"),
        )
        con.execute(
            "INSERT INTO agent_memory(tenant_id, timestamp, agent_role, content, embedding, metadata, importance_score, category) VALUES (?,?,?,?,?,?,?,?)",
            ("TENANT_A", fresh, "agent", "Fresh km", sqlite3.Binary(b"\x00\x00\x80?"), "{}", 5, "KNOWLEDGE_MEMORY"),
        )
        con.commit()
    finally:
        con.close()

    deleted = manager.cleanup_knowledge_memory(days=60)
    assert deleted == 1

    con = sqlite3.connect(db_path)
    try:
        remaining = con.execute("SELECT content FROM agent_memory ORDER BY content").fetchall()
        audit_actions = con.execute("SELECT action FROM memory_audit_log ORDER BY created_at").fetchall()
    finally:
        con.close()

    assert remaining == [("Fresh km",)]
    assert ("delete",) in audit_actions


def test_knowledge_memory_topic_retrieval_parses_legacy_and_canonical_utc_timestamps(tmp_path):
    db_path = tmp_path / "auth.sqlite3"
    _setup_db(str(db_path))
    manager = MemoryManager(str(db_path))

    now = datetime.now(timezone.utc)
    canonical_recent = (now - timedelta(days=1)).isoformat().replace("+00:00", "Z")
    legacy_stale = (now - timedelta(days=30)).isoformat() + "Z"

    con = sqlite3.connect(db_path)
    try:
        con.execute(
            "INSERT INTO agent_memory(tenant_id, timestamp, agent_role, content, embedding, metadata, importance_score, category) VALUES (?,?,?,?,?,?,?,?)",
            (
                "TENANT_A",
                canonical_recent,
                "agent",
                "Neue Notiz",
                sqlite3.Binary(b"\x00\x00\x80?"),
                '{"topic":"contacts","memory_type":"note"}',
                5,
                "KNOWLEDGE_MEMORY",
            ),
        )
        con.execute(
            "INSERT INTO agent_memory(tenant_id, timestamp, agent_role, content, embedding, metadata, importance_score, category) VALUES (?,?,?,?,?,?,?,?)",
            (
                "TENANT_A",
                legacy_stale,
                "agent",
                "Alte Notiz",
                sqlite3.Binary(b"\x00\x00\x80?"),
                '{"topic":"contacts","memory_type":"note"}',
                5,
                "KNOWLEDGE_MEMORY",
            ),
        )
        con.commit()
    finally:
        con.close()

    hits = manager.retrieve_by_topic(tenant_id="TENANT_A", topic="contacts", limit=2, recency_days=60)
    assert len(hits) == 2
    assert hits[0]["content"] == "Neue Notiz"
    assert hits[0]["score"] > hits[1]["score"]
