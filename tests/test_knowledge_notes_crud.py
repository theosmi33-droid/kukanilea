from __future__ import annotations

import sqlite3
from pathlib import Path

import kukanilea_core_v3_fixed as core
from app import create_app
from app.knowledge.core import (
    knowledge_note_create,
    knowledge_note_delete,
    knowledge_note_update,
)


def _init_core(tmp_path: Path) -> None:
    core.DB_PATH = tmp_path / "core.db"
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()


def _client(tmp_path: Path, read_only: bool = False):
    _init_core(tmp_path)
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test", READ_ONLY=read_only)
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user"] = "dev"
        sess["role"] = "OPERATOR"
        sess["tenant_id"] = "TENANT_A"
    return client


def test_notes_crud_and_pii_free_event_payload(tmp_path: Path) -> None:
    _init_core(tmp_path)

    note = knowledge_note_create("TENANT_A", "dev", "Titel", "Body geheim", "alpha")
    assert note["chunk_id"]

    updated = knowledge_note_update(
        "TENANT_A", note["chunk_id"], "dev", "Titel2", "Body2", "beta"
    )
    assert updated["title"] == "Titel2"

    knowledge_note_delete("TENANT_A", note["chunk_id"], "dev")

    con = sqlite3.connect(str(core.DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        events = con.execute(
            """
            SELECT event_type, payload_json
            FROM events
            WHERE event_type IN ('knowledge_note_created','knowledge_note_updated','knowledge_note_deleted')
            ORDER BY id ASC
            """
        ).fetchall()
        assert len(events) == 3
        for e in events:
            payload = str(e["payload_json"])
            assert "Body geheim" not in payload
            assert "Titel" not in payload
    finally:
        con.close()


def test_read_only_blocks_note_mutations_route(tmp_path: Path) -> None:
    client = _client(tmp_path, read_only=True)

    resp = client.post(
        "/api/knowledge/notes",
        json={"title": "x", "body": "y", "tags": "z"},
    )
    assert resp.status_code == 403
    payload = resp.get_json() or {}
    assert payload.get("error", {}).get("code") == "read_only"
