from __future__ import annotations

import csv
import io
import sqlite3

from app import core


def test_flow_c_export_is_deterministic_for_equal_timestamps(auth_client):
    app = auth_client.application
    with app.app_context():
        tenant = "KUKANILEA"
        started_at = "2026-03-01T08:00:00+00:00"
        first = core.time_entry_start(tenant_id=tenant, user="admin", started_at=started_at)
        core.time_entry_stop(
            tenant_id=tenant,
            user="admin",
            entry_id=int(first["id"]),
            ended_at="2026-03-01T08:30:00+00:00",
        )

        second = core.time_entry_start(tenant_id=tenant, user="admin", started_at=started_at)
        core.time_entry_stop(
            tenant_id=tenant,
            user="admin",
            entry_id=int(second["id"]),
            ended_at="2026-03-01T09:15:00+00:00",
        )

        baseline = core.time_entries_export_csv(tenant_id=tenant, user="admin")
        for _ in range(5):
            assert core.time_entries_export_csv(tenant_id=tenant, user="admin") == baseline

        rows = list(csv.DictReader(io.StringIO(baseline)))
        assert [int(rows[0]["entry_id"]), int(rows[1]["entry_id"])] == [
            int(second["id"]),
            int(first["id"]),
        ]


def test_flow_c_offline_timer_recovery_persists_running_entry(auth_client):
    app = auth_client.application
    with app.app_context():
        tenant = "KUKANILEA"
        running = core.time_entry_start(
            tenant_id=tenant,
            user="admin",
            started_at="2026-03-01T10:00:00+00:00",
        )

        db_path = app.config["CORE_DB"]
        with sqlite3.connect(db_path) as con:
            row = con.execute(
                "SELECT id, end_at FROM time_entries WHERE id=?",
                (int(running["id"]),),
            ).fetchone()
            assert row is not None
            assert row[1] is None

        stopped = core.time_entry_stop(
            tenant_id=tenant,
            user="admin",
            entry_id=int(running["id"]),
            ended_at="2026-03-01T11:00:00+00:00",
        )
        assert stopped["duration_seconds"] == 3600


def test_flow_c_nachtrag_and_storno_are_auditable(auth_client):
    app = auth_client.application
    with app.app_context():
        tenant = "KUKANILEA"
        entry = core.time_entry_start(
            tenant_id=tenant,
            user="admin",
            started_at="2026-03-02T10:00:00+00:00",
            note="Initial",
        )
        core.time_entry_stop(
            tenant_id=tenant,
            user="admin",
            entry_id=int(entry["id"]),
            ended_at="2026-03-02T11:00:00+00:00",
        )

        # Nachtrag (retroactive correction)
        core.time_entry_update(
            tenant_id=tenant,
            entry_id=int(entry["id"]),
            end_at="2026-03-02T11:30:00+00:00",
            note="Nachtrag: Abstimmung ergänzt",
            user="admin",
        )

        # Storno via explicit correction to zero duration + marker note.
        core.time_entry_update(
            tenant_id=tenant,
            entry_id=int(entry["id"]),
            end_at="2026-03-02T10:00:00+00:00",
            note="STORNO: Fehlbuchung",
            user="admin",
        )

        with sqlite3.connect(app.config["CORE_DB"]) as con:
            con.row_factory = sqlite3.Row
            audit_rows = con.execute(
                "SELECT action, meta_json FROM audit WHERE target=? ORDER BY id",
                (str(entry["id"]),),
            ).fetchall()

        actions = [row["action"] for row in audit_rows]
        assert "TIME_ENTRY_START" in actions
        assert "TIME_ENTRY_STOP" in actions
        assert actions.count("TIME_ENTRY_EDIT") >= 2
