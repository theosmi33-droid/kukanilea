from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from app.eventlog import core as ev
import kukanilea_core_v3_fixed as core


def _set_db(tmp_path: Path, monkeypatch) -> Path:
    db = tmp_path / "core.sqlite3"
    monkeypatch.setattr(ev.Config, "CORE_DB", db)
    return db


def _init_core(tmp_path: Path, monkeypatch) -> Path:
    db = _set_db(tmp_path, monkeypatch)
    core.DB_PATH = db
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()
    ev.ensure_eventlog_schema()
    return db


def _last_event(db: Path) -> dict:
    con = sqlite3.connect(str(db))
    con.row_factory = sqlite3.Row
    try:
        row = con.execute("SELECT * FROM events ORDER BY id DESC LIMIT 1").fetchone()
        assert row is not None
        out = dict(row)
        out["payload"] = json.loads(out.get("payload_json") or "{}")
        return out
    finally:
        con.close()


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


def test_timer_start_event_written_and_chain_ok(tmp_path: Path, monkeypatch) -> None:
    db = _init_core(tmp_path, monkeypatch)
    project = core.time_project_create(tenant_id="TENANT1", name="P1", created_by="dev")

    entry = core.time_entry_start(
        tenant_id="TENANT1",
        user="alice",
        project_id=int(project["id"]),
        user_id=42,
        started_at="2026-02-01T09:00:00",
    )

    event = _last_event(db)
    assert event["event_type"] == "timer_started"
    assert event["entity_type"] == "time_entry"
    assert event["entity_id"] == int(entry["id"])
    payload = event["payload"]
    assert payload["schema_version"] == 1
    assert payload["data"]["task_id"] is None
    assert payload["data"]["start_time"] == "2026-02-01T09:00:00"

    ok, bad_id, reason = ev.event_verify_chain()
    assert ok is True and bad_id is None and reason is None


def test_timer_stop_event_written_duration_matches_db_and_chain_ok(
    tmp_path: Path, monkeypatch
) -> None:
    db = _init_core(tmp_path, monkeypatch)
    project = core.time_project_create(tenant_id="TENANT1", name="P1", created_by="dev")
    started = core.time_entry_start(
        tenant_id="TENANT1",
        user="alice",
        project_id=int(project["id"]),
        user_id=7,
        started_at="2026-02-01T10:00:00",
    )
    stopped = core.time_entry_stop(
        tenant_id="TENANT1",
        user="alice",
        entry_id=int(started["id"]),
        ended_at="2026-02-01T11:30:00",
    )

    event = _last_event(db)
    assert event["event_type"] == "timer_stopped"
    assert event["entity_type"] == "time_entry"
    assert event["entity_id"] == int(started["id"])
    payload = event["payload"]
    assert payload["schema_version"] == 1
    assert payload["data"]["duration"] == int(stopped["duration"])
    assert payload["data"]["end_time"] == "2026-02-01T11:30:00"

    ok, bad_id, reason = ev.event_verify_chain()
    assert ok is True and bad_id is None and reason is None


def test_time_entry_edit_event_contains_before_after(tmp_path: Path, monkeypatch) -> None:
    db = _init_core(tmp_path, monkeypatch)
    project = core.time_project_create(tenant_id="TENANT1", name="P1", created_by="dev")
    entry = core.time_entry_start(
        tenant_id="TENANT1",
        user="alice",
        project_id=int(project["id"]),
        user_id=9,
        started_at="2026-02-01T12:00:00",
    )

    core.time_entry_update(
        tenant_id="TENANT1",
        entry_id=int(entry["id"]),
        note="updated",
        end_at="2026-02-01T12:20:00",
        user="alice",
    )

    event = _last_event(db)
    assert event["event_type"] == "time_entry_edited"
    assert event["entity_type"] == "time_entry"
    assert event["entity_id"] == int(entry["id"])
    payload = event["payload"]
    assert payload["schema_version"] == 1
    assert "before" in payload["data"]
    assert "after" in payload["data"]
    assert payload["data"]["before"]["note"] in {"", None}
    assert payload["data"]["after"]["note"] == "updated"

    ok, bad_id, reason = ev.event_verify_chain()
    assert ok is True and bad_id is None and reason is None


def test_project_budget_update_event_contains_before_after(
    tmp_path: Path, monkeypatch
) -> None:
    db = _init_core(tmp_path, monkeypatch)
    project = core.time_project_create(
        tenant_id="TENANT1",
        name="Budget",
        budget_hours=8,
        budget_cost=800.0,
        created_by="dev",
    )

    summary = core.time_project_update_budget(
        tenant_id="TENANT1",
        project_id=int(project["id"]),
        budget_hours=10,
        budget_cost=1200.0,
        user_id=101,
    )
    assert summary["updated_budget_hours"] == 10
    assert summary["updated_budget_cost"] == 1200.0

    event = _last_event(db)
    assert event["event_type"] == "project_budget_updated"
    assert event["entity_type"] == "project"
    assert event["entity_id"] == int(project["id"])
    payload = event["payload"]
    assert payload["schema_version"] == 1
    assert payload["data"]["before"]["budget_hours"] == 8
    assert payload["data"]["after"]["budget_hours"] == 10
    assert payload["data"]["after"]["budget_cost"] == 1200.0

    ok, bad_id, reason = ev.event_verify_chain()
    assert ok is True and bad_id is None and reason is None
