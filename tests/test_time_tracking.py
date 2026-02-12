from pathlib import Path

import pytest

import kukanilea_core_v3_fixed as core


def _init_core(tmp_path: Path) -> None:
    core.DB_PATH = tmp_path / "core.db"
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()


def test_time_tracking_one_running_timer(tmp_path: Path) -> None:
    _init_core(tmp_path)
    project = core.time_project_create(
        tenant_id="TENANT1", name="Projekt A", created_by="dev"
    )
    entry = core.time_entry_start(
        tenant_id="TENANT1", user="alice", project_id=project["id"]
    )
    assert entry["end_at"] is None
    with pytest.raises(ValueError):
        core.time_entry_start(
            tenant_id="TENANT1", user="alice", project_id=project["id"]
        )
    stopped = core.time_entry_stop(tenant_id="TENANT1", user="alice")
    assert stopped["end_at"]
    assert stopped["duration_seconds"] >= 0


def test_time_tracking_tenant_isolation(tmp_path: Path) -> None:
    _init_core(tmp_path)
    p1 = core.time_project_create(tenant_id="TENANT1", name="T1", created_by="dev")
    p2 = core.time_project_create(tenant_id="TENANT2", name="T2", created_by="dev")
    core.time_entry_start(tenant_id="TENANT1", user="alice", project_id=p1["id"])
    core.time_entry_stop(tenant_id="TENANT1", user="alice")
    core.time_entry_start(tenant_id="TENANT2", user="bob", project_id=p2["id"])
    core.time_entry_stop(tenant_id="TENANT2", user="bob")
    entries_t1 = core.time_entries_list(tenant_id="TENANT1")
    assert entries_t1
    assert all(e["tenant_id"] == "TENANT1" for e in entries_t1)


def test_time_tracking_export_csv(tmp_path: Path) -> None:
    _init_core(tmp_path)
    project = core.time_project_create(
        tenant_id="TENANT1", name="Export", created_by="dev"
    )
    core.time_entry_start(tenant_id="TENANT1", user="alice", project_id=project["id"])
    core.time_entry_stop(tenant_id="TENANT1", user="alice")
    csv_payload = core.time_entries_export_csv(
        tenant_id="TENANT1",
        start_at="2000-01-01T00:00:00",
        end_at="2100-01-01T00:00:00",
    )
    lines = csv_payload.strip().splitlines()
    assert lines[0].startswith("entry_id,project_id,project_name,user")
    assert any("Export" in line for line in lines[1:])


def test_time_tracking_task_and_project_summary(tmp_path: Path) -> None:
    _init_core(tmp_path)
    project = core.time_project_create(
        tenant_id="TENANT1",
        name="Budget Projekt",
        budget_hours=1,
        budget_cost=120.0,
        created_by="dev",
    )
    task_id = core.task_create(
        tenant="TENANT1",
        severity="INFO",
        task_type="GENERAL",
        title="Zeiterfassung",
        details="Budgettest",
        created_by="dev",
    )
    core.time_entry_start(
        tenant_id="TENANT1",
        user="alice",
        project_id=project["id"],
        task_id=task_id,
        started_at="2026-01-01T10:00:00",
    )
    core.time_entry_stop(
        tenant_id="TENANT1",
        user="alice",
        ended_at="2026-01-01T11:30:00",
    )

    task_summary = core.time_entries_summary_by_task(
        tenant_id="TENANT1", task_id=task_id
    )
    assert task_summary["total_entries"] == 1
    assert task_summary["total_seconds"] == 5400

    project_summary = core.time_entries_summary_by_project(
        tenant_id="TENANT1", project_id=project["id"]
    )
    assert project_summary["spent_hours"] == 1.5
    assert project_summary["warning"] is True
