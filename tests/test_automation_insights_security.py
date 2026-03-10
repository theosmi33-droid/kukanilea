from __future__ import annotations

import sqlite3
import threading

from app.modules.automation.insights import generate_daily_insights


def _connect(path: str) -> sqlite3.Connection:
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    return con


def test_collision_count_matches_exact_tenant_id(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "insights.db"

    con = _connect(str(db_path))
    con.executescript(
        """
        CREATE TABLE leads (
            id INTEGER PRIMARY KEY,
            tenant_id TEXT,
            created_at TEXT,
            response_due TEXT,
            status TEXT,
            priority TEXT,
            assigned_to TEXT
        );
        CREATE TABLE tasks (
            id INTEGER PRIMARY KEY,
            tenant TEXT,
            status TEXT
        );
        CREATE TABLE events (
            id INTEGER PRIMARY KEY,
            event_type TEXT,
            entity_type TEXT,
            ts TEXT,
            payload_json TEXT
        );
        """
    )
    con.execute(
        "INSERT INTO events(event_type, entity_type, ts, payload_json) VALUES (?,?,datetime('now'),?)",
        ("lead_claim_collision", "lead", '{"tenant_id":"tenantA"}'),
    )
    con.execute(
        "INSERT INTO events(event_type, entity_type, ts, payload_json) VALUES (?,?,datetime('now'),?)",
        ("lead_claim_collision", "lead", '{"tenant_id":"tenantB"}'),
    )
    con.commit()
    con.close()

    monkeypatch.setattr("app.modules.automation.insights.legacy_core._DB_LOCK", threading.Lock())
    monkeypatch.setattr(
        "app.modules.automation.insights.legacy_core._db",
        lambda: _connect(str(db_path)),
    )

    monkeypatch.setattr("app.modules.automation.insights.automation_latest_run", lambda _tenant: None)

    payload = generate_daily_insights("tenant%", "2026-01-01")

    assert payload["claim_collisions_count"] == 0
