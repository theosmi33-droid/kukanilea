from __future__ import annotations

from pathlib import Path

from app.ai import memory
from app.config import Config


def test_ai_memory_save_and_feedback(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "core.sqlite3"
    monkeypatch.setattr(Config, "CORE_DB", db_path)

    conv_id = memory.save_conversation(
        tenant_id="TENANT_A",
        user_id="dev",
        user_message="Kontakt: max@example.com",
        assistant_response="Antwort an max@example.com",
        tools_used=["search_contacts"],
    )
    assert conv_id

    rows = memory.list_recent_conversations(
        tenant_id="TENANT_A", user_id="dev", limit=5
    )
    assert rows
    assert "[redacted-email]" in rows[0]["user_message"].lower()

    feedback_id = memory.add_feedback(
        tenant_id="TENANT_A", conversation_id=conv_id, rating="positive"
    )
    assert feedback_id
