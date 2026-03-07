from __future__ import annotations

import sqlite3
from pathlib import Path

from app.eventlog import core


def _rows(db_path: Path) -> list[sqlite3.Row]:
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        return con.execute("SELECT * FROM events ORDER BY id ASC").fetchall()
    finally:
        con.close()


def test_event_is_written_with_iso8601_timestamp(monkeypatch, tmp_path):
    db_path = tmp_path / "core.sqlite3"
    monkeypatch.setattr(core.Config, "CORE_DB", db_path)

    event_id = core.event_append(
        event_type="ticket.created",
        entity_type="ticket",
        entity_id=1,
        payload={"b": 2, "a": 1},
    )

    assert event_id == 1
    rows = _rows(db_path)
    assert len(rows) == 1
    assert rows[0]["ts"].endswith("Z")


def test_follow_up_entry_references_previous_hash(monkeypatch, tmp_path):
    db_path = tmp_path / "core.sqlite3"
    monkeypatch.setattr(core.Config, "CORE_DB", db_path)

    first_id = core.event_append(
        event_type="ticket.created",
        entity_type="ticket",
        entity_id=100,
        payload={"status": "new"},
    )
    second_id = core.event_append(
        event_type="ticket.updated",
        entity_type="ticket",
        entity_id=100,
        payload={"status": "open"},
    )

    assert (first_id, second_id) == (1, 2)
    rows = _rows(db_path)
    assert rows[1]["prev_hash"] == rows[0]["hash"]


def test_verify_detects_tampering(monkeypatch, tmp_path):
    db_path = tmp_path / "core.sqlite3"
    monkeypatch.setattr(core.Config, "CORE_DB", db_path)

    core.event_append(
        event_type="ticket.created",
        entity_type="ticket",
        entity_id=9,
        payload={"status": "new"},
    )

    con = sqlite3.connect(str(db_path))
    try:
        con.execute("UPDATE events SET payload_json=? WHERE id=1", ('{"status":"tampered"}',))
        con.commit()
    finally:
        con.close()

    ok, first_bad_id, reason = core.event_verify_chain()
    assert ok is False
    assert first_bad_id == 1
    assert reason == "hash_mismatch"
