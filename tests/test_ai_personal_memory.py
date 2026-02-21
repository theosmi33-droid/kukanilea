from __future__ import annotations

from pathlib import Path

from app.ai import personal_memory
from app.config import Config


def test_personal_memory_add_list_and_context(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "ai_memory.sqlite3"
    monkeypatch.setattr(Config, "AI_MEMORY_DB", db_path)

    note_id = personal_memory.add_user_note(
        tenant_id="TENANT_A",
        user_id="dev",
        note="Merke meine bevorzugte Sprache ist Deutsch.",
    )
    assert note_id

    rows = personal_memory.list_user_notes(
        tenant_id="TENANT_A", user_id="dev", limit=10
    )
    assert len(rows) == 1
    assert "deutsch" in rows[0]["note"].lower()

    ctx = personal_memory.render_user_memory_context(
        tenant_id="TENANT_A",
        user_id="dev",
        limit=5,
    )
    assert "Persoenliche Notizen" in ctx
    assert "deutsch" in ctx.lower()


def test_personal_memory_deduplicates_same_note(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "ai_memory.sqlite3"
    monkeypatch.setattr(Config, "AI_MEMORY_DB", db_path)

    first = personal_memory.add_user_note(
        tenant_id="TENANT_A",
        user_id="dev",
        note="Kontakt bevorzugt Telefon.",
    )
    second = personal_memory.add_user_note(
        tenant_id="TENANT_A",
        user_id="dev",
        note="Kontakt bevorzugt Telefon.",
    )
    assert first == second
    assert personal_memory.count_user_notes(tenant_id="TENANT_A", user_id="dev") == 1
