from __future__ import annotations

import os
import sys
import tempfile
import sqlite3
from pathlib import Path
from unittest.mock import patch

# Ensure we can import app
sys.path.append(os.getcwd())

from app.agents.memory_store import MemoryManager

def test_memory_system():
    print("Testing KUKANILEA Native Memory System...")

    with tempfile.NamedTemporaryFile() as tmp:
        db_path = tmp.name
        con = sqlite3.connect(db_path)
        con.execute("""
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
        """)
        con.commit()
        con.close()

        manager = MemoryManager(db_path)

        # Mock embeddings: simple deterministic floats
        def mock_embed(text):
            if "Zahlungsfrist" in text: return [1.0, 0.0, 0.0]
            if "Lieferzeit" in text: return [0.0, 1.0, 0.0]
            if "Frist" in text: return [0.9, 0.1, 0.0]
            return [0.0, 0.0, 1.0]

        with patch("app.agents.memory_store.generate_embedding", side_effect=mock_embed):
            # 1. Store memories
            print("Storing memories...")
            manager.store_memory("tenant_A", "system", "Die Zahlungsfrist beträgt 14 Tage.")
            manager.store_memory("tenant_A", "system", "Die Lieferzeit beträgt 5 Werktage.")
            manager.store_memory("tenant_B", "system", "Geheime Info von B.")

            # 2. Retrieve context (Tenant Isolation Check)
            print("Retrieving context for Tenant A...")
            results = manager.retrieve_context("tenant_A", "Wie lange ist die Frist?", limit=1)

            assert len(results) == 1
            assert "Zahlungsfrist" in results[0]["content"]
            assert results[0]["score"] > 0.8
            print(f"Result: {results[0]['content']} (Score: {results[0]['score']:.4f})")

            # 3. Security Check: Tenant B should NOT see A's data
            print("Checking Tenant Isolation...")
            results_B = manager.retrieve_context("tenant_B", "Zahlungsfrist")
            for r in results_B:
                assert "Zahlungsfrist" not in r["content"]
            print("Tenant Isolation: OK")

    print("Memory System Test: PASS")

if __name__ == "__main__":
    test_memory_system()


def test_chatbot_memory_requires_nonempty_tenant_id(tmp_path: Path):
    db_path = tmp_path / "memory.sqlite3"
    con = sqlite3.connect(db_path)
    con.execute("""
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
    """)
    con.commit()
    con.close()

    manager = MemoryManager(str(db_path))

    with patch("app.agents.memory_store.generate_embedding", return_value=[0.1, 0.2, 0.3]):
        assert manager.store_memory("", "chatbot", "sensitive") is False
        assert manager.retrieve_context("", "sensitive") == []

        assert manager.store_messenger_message(
            tenant_id="TENANT_OK",
            provider="internal",
            sender="u",
            recipient="bot",
            content="chat-memory",
        ) is True

    con = sqlite3.connect(db_path)
    try:
        rows = con.execute("SELECT tenant_id, agent_role, category FROM agent_memory").fetchall()
    finally:
        con.close()

    assert rows == [("TENANT_OK", "messenger", "MESSENGER_MESSAGE")]
