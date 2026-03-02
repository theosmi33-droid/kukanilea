from __future__ import annotations

import csv
import io
from pathlib import Path

import pytest

from app import core, create_app


def _seed_time_data() -> None:
    core.time_project_create(
        tenant_id="SYSTEM",
        name="Projekt A",
        description="",
        created_by="admin",
    )
    core.time_project_create(
        tenant_id="SYSTEM",
        name="Projekt B",
        description="",
        created_by="admin",
    )


@pytest.fixture()
def isolated_core_db(tmp_path: Path):
    db_path = tmp_path / "time_domain.sqlite3"
    core.set_db_path(db_path)
    core.db_init()
    _seed_time_data()
    yield db_path


def test_timer_state_machine(isolated_core_db: Path):
    started = core.time_entry_start(
        tenant_id="SYSTEM",
        user="alice",
        project_id=1,
        task_ref="TASK-1",
        note="Start",
        started_at="2026-03-01T08:00:00",
    )
    assert started["end_at"] is None

    with pytest.raises(ValueError, match="running_timer_exists"):
        core.time_entry_start(
            tenant_id="SYSTEM",
            user="alice",
            project_id=1,
            note="Start2",
            started_at="2026-03-01T08:10:00",
        )

    stopped = core.time_entry_stop(
        tenant_id="SYSTEM",
        user="alice",
        ended_at="2026-03-01T08:05:00",
    )
    assert int(stopped["duration_seconds"]) == 300
    assert stopped["entry_type"] == "TIMER"

    with pytest.raises(ValueError, match="no_running_timer"):
        core.time_entry_stop(
            tenant_id="SYSTEM",
            user="alice",
            ended_at="2026-03-01T08:10:00",
        )


def test_permissions_user_vs_admin(isolated_core_db: Path):
    core.time_entry_manual_create(
        tenant_id="SYSTEM",
        user="alice",
        start_at="2026-03-01T09:00:00",
        end_at="2026-03-01T10:00:00",
        project_id=1,
        task_ref="TASK-A",
    )
    bob = core.time_entry_manual_create(
        tenant_id="SYSTEM",
        user="bob",
        start_at="2026-03-01T10:00:00",
        end_at="2026-03-01T11:00:00",
        project_id=2,
        task_ref="TASK-B",
    )

    app = create_app()
    client = app.test_client()

    with client.session_transaction() as sess:
        sess["user"] = "alice"
        sess["role"] = "OPERATOR"
        sess["tenant_id"] = "SYSTEM"
        sess["tenant_db_path"] = str(isolated_core_db)
    res_user = client.get("/api/time/entries?range=month&date=2026-03-01&user=bob")
    assert res_user.status_code == 200
    payload_user = res_user.get_json()
    assert payload_user["ok"] is True
    assert payload_user["entries"]
    assert all(row["user"] == "alice" for row in payload_user["entries"])

    with client.session_transaction() as sess:
        sess["user"] = "admin"
        sess["role"] = "ADMIN"
        sess["tenant_id"] = "SYSTEM"
        sess["tenant_db_path"] = str(isolated_core_db)
    res_admin = client.get("/api/time/entries?range=month&date=2026-03-01&user=bob")
    assert res_admin.status_code == 200
    payload_admin = res_admin.get_json()
    assert payload_admin["ok"] is True
    assert any(int(row["id"]) == int(bob["id"]) for row in payload_admin["entries"])
    assert all(row["user"] == "bob" for row in payload_admin["entries"])


def test_export_format_includes_gobd_fields(isolated_core_db: Path):
    core.time_entry_manual_create(
        tenant_id="SYSTEM",
        user="alice",
        start_at="2026-03-01T12:00:00",
        end_at="2026-03-01T13:30:00",
        project_id=1,
        task_ref="TASK-EXPORT-1",
        note="Arbeitsblock",
    )
    storno_target = core.time_entry_manual_create(
        tenant_id="SYSTEM",
        user="alice",
        start_at="2026-03-01T14:00:00",
        end_at="2026-03-01T14:15:00",
        project_id=1,
        task_ref="TASK-EXPORT-2",
        note="Fehlbuchung",
    )
    core.time_entry_storno(
        tenant_id="SYSTEM",
        entry_id=int(storno_target["id"]),
        cancelled_by="alice",
        reason="Falsche Zuordnung",
    )

    app = create_app()
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user"] = "admin"
        sess["role"] = "ADMIN"
        sess["tenant_id"] = "SYSTEM"
        sess["tenant_db_path"] = str(isolated_core_db)

    res = client.get("/api/time/export?range=day&date=2026-03-01")
    assert res.status_code == 200
    assert "text/csv" in (res.headers.get("Content-Type") or "")

    rows = list(csv.DictReader(io.StringIO(res.data.decode("utf-8"))))
    assert rows
    first = rows[0]
    required = {
        "user",
        "project_name",
        "task_ref",
        "start_at",
        "end_at",
        "duration_seconds",
        "is_cancelled",
        "entry_hash",
        "previous_entry_hash",
    }
    assert required.issubset(set(first.keys()))
    assert any(row.get("is_cancelled") == "1" for row in rows)
