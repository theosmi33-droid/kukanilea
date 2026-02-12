from __future__ import annotations

import sqlite3
from pathlib import Path

from app.derived import views


def _seed_db(path: Path) -> None:
    con = sqlite3.connect(str(path))
    try:
        con.execute(
            """
            CREATE TABLE events(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              ts TEXT NOT NULL,
              event_type TEXT NOT NULL,
              entity_type TEXT NOT NULL,
              entity_id INTEGER NOT NULL,
              payload_json TEXT NOT NULL,
              prev_hash TEXT NOT NULL,
              hash TEXT NOT NULL UNIQUE
            )
            """
        )
        con.execute(
            """
            CREATE TABLE time_projects(
              id INTEGER PRIMARY KEY,
              tenant_id TEXT NOT NULL,
              name TEXT NOT NULL,
              budget_hours REAL,
              budget_cost REAL
            )
            """
        )
        con.execute(
            """
            CREATE TABLE time_entries(
              id INTEGER PRIMARY KEY,
              tenant_id TEXT NOT NULL,
              project_id INTEGER,
              duration_seconds INTEGER,
              duration INTEGER
            )
            """
        )

        con.execute(
            "INSERT INTO events(ts,event_type,entity_type,entity_id,payload_json,prev_hash,hash) VALUES (?,?,?,?,?,?,?)",
            (
                "2026-01-01T10:00:00+00:00",
                "timer_started",
                "task",
                7,
                '{"user_id":1,"task_id":7,"start_time":"2026-01-01T10:00:00+00:00"}',
                "0" * 64,
                "a" * 64,
            ),
        )
        con.execute(
            "INSERT INTO events(ts,event_type,entity_type,entity_id,payload_json,prev_hash,hash) VALUES (?,?,?,?,?,?,?)",
            (
                "2026-01-01T10:05:00+00:00",
                "timer_started",
                "task",
                8,
                '{"user_id":2,"task_id":8,"start_time":"2026-01-01T10:05:00+00:00"}',
                "a" * 64,
                "b" * 64,
            ),
        )
        con.execute(
            "INSERT INTO events(ts,event_type,entity_type,entity_id,payload_json,prev_hash,hash) VALUES (?,?,?,?,?,?,?)",
            (
                "2026-01-01T11:00:00+00:00",
                "timer_stopped",
                "task",
                7,
                '{"user_id":1}',
                "b" * 64,
                "c" * 64,
            ),
        )

        con.execute(
            "INSERT INTO time_projects(id, tenant_id, name, budget_hours, budget_cost) VALUES (1,'TENANT1','Projekt A',10,1000)"
        )
        con.execute(
            "INSERT INTO time_entries(id, tenant_id, project_id, duration_seconds, duration) VALUES (1,'TENANT1',1,7200,7200)"
        )
        con.commit()
    finally:
        con.close()


def test_rebuild_active_timers_and_budget(tmp_path: Path, monkeypatch) -> None:
    db = tmp_path / "core.sqlite3"
    _seed_db(db)
    monkeypatch.setattr(views.Config, "CORE_DB", db)

    active_rows = views.rebuild_active_timers()
    assert active_rows == 1

    budget_rows = views.rebuild_budget_progress()
    assert budget_rows == 1

    con = sqlite3.connect(str(db))
    con.row_factory = sqlite3.Row
    try:
        active = con.execute("SELECT * FROM derived_active_timers").fetchall()
        assert len(active) == 1
        assert int(active[0]["user_id"]) == 2
        assert int(active[0]["task_id"]) == 8

        budget = con.execute(
            "SELECT * FROM derived_budget_progress WHERE project_id=1"
        ).fetchone()
        assert budget is not None
        assert float(budget["total_hours"]) == 2.0
        assert float(budget["hours_percent"]) == 20.0
    finally:
        con.close()
