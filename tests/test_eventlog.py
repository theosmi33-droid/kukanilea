from __future__ import annotations

import sqlite3
from pathlib import Path

from app.eventlog import core as ev


def _set_db(tmp_path: Path, monkeypatch) -> Path:
    db = tmp_path / "core.sqlite3"
    monkeypatch.setattr(ev.Config, "CORE_DB", db)
    return db


def test_event_append_verify_and_history(tmp_path: Path, monkeypatch) -> None:
    db = _set_db(tmp_path, monkeypatch)
    ev.ensure_eventlog_schema()

    e1 = ev.event_append("timer_started", "task", 10, {"user_id": 1, "task_id": 10})
    e2 = ev.event_append("timer_stopped", "task", 10, {"user_id": 1})
    assert e1 > 0 and e2 > e1

    ok, bad_id, reason = ev.event_verify_chain()
    assert ok is True
    assert bad_id is None
    assert reason is None

    hist = ev.event_get_history("task", 10, limit=10)
    assert len(hist) == 2
    assert hist[0]["event_type"] == "timer_stopped"

    con = sqlite3.connect(str(db))
    try:
        row = con.execute("SELECT hash FROM events WHERE id=?", (e1,)).fetchone()
        assert row and len(row[0]) == 64
    finally:
        con.close()


def test_event_verify_detects_chain_break(tmp_path: Path, monkeypatch) -> None:
    db = _set_db(tmp_path, monkeypatch)
    ev.ensure_eventlog_schema()
    ev.event_append("x1", "task", 1, {"a": 1})
    second = ev.event_append("x2", "task", 1, {"a": 2})

    con = sqlite3.connect(str(db))
    try:
        con.execute("UPDATE events SET prev_hash='broken' WHERE id=?", (second,))
        con.commit()
    finally:
        con.close()

    ok, bad_id, reason = ev.event_verify_chain()
    assert ok is False
    assert bad_id == second
    assert reason == "prev_hash_mismatch"


def test_event_hash_collision_resistance_signal(tmp_path: Path, monkeypatch) -> None:
    _set_db(tmp_path, monkeypatch)
    h1 = ev.event_hash("0" * 64, "2026-01-01T00:00:00+00:00", "a", "task", 1, "{}")
    h2 = ev.event_hash("1" * 64, "2026-01-01T00:00:00+00:00", "a", "task", 1, "{}")
    assert h1 != h2
