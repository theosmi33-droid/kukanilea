from __future__ import annotations

import sqlite3
from pathlib import Path

import kukanilea_core_v3_fixed as core
from app.knowledge.core import knowledge_note_create


def _init_core(tmp_path: Path) -> None:
    core.DB_PATH = tmp_path / "core.db"
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()


def test_pii_redaction_applied_and_event_payload_has_no_pii(tmp_path: Path) -> None:
    _init_core(tmp_path)
    note = knowledge_note_create(
        "TENANT_A",
        "dev",
        "Kontakt",
        "Mail max@example.com\nTelefon +49 123 456 7890\nKonto 123456789",
        "privat",
    )

    con = sqlite3.connect(str(core.DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            "SELECT body FROM knowledge_chunks WHERE tenant_id=? AND chunk_id=? LIMIT 1",
            ("TENANT_A", note["chunk_id"]),
        ).fetchone()
        assert row is not None
        body = str(row["body"])
        assert "max@example.com" not in body
        assert "+49 123 456 7890" not in body
        assert "123456789" not in body
        assert "[redacted-email]" in body
        assert "[redacted-phone]" in body

        payload = con.execute(
            "SELECT payload_json FROM events WHERE event_type='knowledge_note_created' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        assert payload is not None
        ptxt = str(payload["payload_json"])
        assert "max@example.com" not in ptxt
        assert "Telefon" not in ptxt
    finally:
        con.close()
