from __future__ import annotations

import sqlite3
from pathlib import Path

import kukanilea_core_v3_fixed as core
from app import create_app
from app.config import Config
from app.eventlog import core as eventlog_core
from app.insights.activation import (
    ACTIVATION_MILESTONES,
    build_activation_report,
    record_activation_milestone,
)


def _init_core(tmp_path: Path) -> None:
    core.DB_PATH = tmp_path / "core.db"
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()


def _client(tmp_path: Path, *, tenant: str = "TENANT_A"):
    _init_core(tmp_path)
    Config.CORE_DB = core.DB_PATH
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test", CORE_DB=core.DB_PATH)
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user"] = "dev"
        sess["role"] = "OPERATOR"
        sess["tenant_id"] = tenant
    return client


def test_record_activation_milestone_is_idempotent(tmp_path: Path) -> None:
    _init_core(tmp_path)
    Config.CORE_DB = core.DB_PATH

    first = record_activation_milestone(
        tenant_id="TENANT_A",
        actor_user_id="dev",
        milestone="first_task",
        source="tests",
    )
    second = record_activation_milestone(
        tenant_id="TENANT_A",
        actor_user_id="dev",
        milestone="first_task",
        source="tests",
    )

    assert first is True
    assert second is False

    con = sqlite3.connect(str(core.DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            """
            SELECT COUNT(*) AS c
            FROM events
            WHERE event_type='activation_milestone'
              AND payload_json LIKE '%"tenant_id":"TENANT_A"%'
              AND payload_json LIKE '%"actor_user_id":"dev"%'
              AND payload_json LIKE '%"milestone":"first_task"%'
            """
        ).fetchone()
        assert int(row["c"] or 0) == 1
    finally:
        con.close()


def test_build_activation_report_tracks_completed_users(
    tmp_path: Path, monkeypatch
) -> None:
    _init_core(tmp_path)
    Config.CORE_DB = core.DB_PATH

    timestamps = iter(
        [
            "2026-02-21T10:00:00+00:00",
            "2026-02-21T10:02:00+00:00",
            "2026-02-21T10:03:00+00:00",
            "2026-02-21T10:04:00+00:00",
            "2026-02-21T10:05:00+00:00",
            "2026-02-21T10:06:00+00:00",
            "2026-02-21T10:07:00+00:00",
        ]
    )
    monkeypatch.setattr(eventlog_core, "_now_iso", lambda: next(timestamps))

    for milestone in ACTIVATION_MILESTONES:
        assert (
            record_activation_milestone(
                tenant_id="TENANT_A",
                actor_user_id="dev",
                milestone=milestone,
                source="tests",
            )
            is True
        )

    assert (
        record_activation_milestone(
            tenant_id="TENANT_A",
            actor_user_id="office",
            milestone="first_login",
            source="tests",
        )
        is True
    )
    assert (
        record_activation_milestone(
            tenant_id="TENANT_A",
            actor_user_id="office",
            milestone="first_task",
            source="tests",
        )
        is True
    )

    report = build_activation_report("TENANT_A")
    totals = report.get("totals") or {}
    duration = report.get("time_to_first_workflow_seconds") or {}

    assert totals.get("users_seen") == 2
    assert totals.get("users_completed") == 1
    assert duration.get("count") == 1
    assert duration.get("p50") == 300
    assert duration.get("p95") == 300


def test_api_tasks_create_records_first_task_milestone(tmp_path: Path) -> None:
    client = _client(tmp_path)

    first = client.post(
        "/api/tasks/create",
        json={
            "title": "Activation KPI Task",
            "task_type": "GENERAL",
            "severity": "INFO",
            "details": "a",
        },
    )
    assert first.status_code == 200

    second = client.post(
        "/api/tasks/create",
        json={
            "title": "Activation KPI Task 2",
            "task_type": "GENERAL",
            "severity": "INFO",
            "details": "b",
        },
    )
    assert second.status_code == 200

    con = sqlite3.connect(str(core.DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            """
            SELECT COUNT(*) AS c
            FROM events
            WHERE event_type='activation_milestone'
              AND payload_json LIKE '%"tenant_id":"TENANT_A"%'
              AND payload_json LIKE '%"actor_user_id":"dev"%'
              AND payload_json LIKE '%"milestone":"first_task"%'
            """
        ).fetchone()
        assert int(row["c"] or 0) == 1
    finally:
        con.close()


def test_api_insights_activation_is_tenant_scoped(tmp_path: Path) -> None:
    client = _client(tmp_path, tenant="TENANT_A")

    for milestone in ACTIVATION_MILESTONES:
        record_activation_milestone(
            tenant_id="TENANT_A",
            actor_user_id="dev",
            milestone=milestone,
            source="tests",
        )

    for milestone in ACTIVATION_MILESTONES:
        record_activation_milestone(
            tenant_id="TENANT_B",
            actor_user_id="other",
            milestone=milestone,
            source="tests",
        )

    resp = client.get("/api/insights/activation")
    assert resp.status_code == 200
    payload = resp.get_json() or {}
    item = payload.get("item") or {}

    assert payload.get("ok") is True
    assert item.get("tenant_id") == "TENANT_A"
    assert (item.get("totals") or {}).get("users_seen") == 1
    assert (item.get("totals") or {}).get("users_completed") == 1
    assert len(item.get("users") or []) == 1
    assert (item.get("users") or [])[0].get("user_id") == "dev"
