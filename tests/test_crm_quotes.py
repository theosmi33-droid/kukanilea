from __future__ import annotations

import sqlite3
from pathlib import Path

import kukanilea_core_v3_fixed as core


def _init_core(tmp_path: Path) -> None:
    core.DB_PATH = tmp_path / "core.db"
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()


def _count_events(db_path: Path, event_type: str) -> int:
    con = sqlite3.connect(str(db_path))
    try:
        row = con.execute(
            "SELECT COUNT(*) FROM events WHERE event_type=?", (event_type,)
        ).fetchone()
        return int(row[0] if row else 0)
    finally:
        con.close()


def test_quote_create_from_deal_generates_items(tmp_path: Path) -> None:
    _init_core(tmp_path)

    project = core.time_project_create(
        tenant_id="TENANT_A",
        name="CRM Projekt",
        budget_hours=10,
        budget_cost=1000.0,
        created_by="dev",
    )
    task_id = core.task_create(
        tenant="TENANT_A",
        severity="INFO",
        task_type="GENERAL",
        title="CRM Arbeit",
        created_by="dev",
    )
    # task/project relation for quote_from_deal
    con = sqlite3.connect(str(core.DB_PATH))
    try:
        con.execute(
            "UPDATE tasks SET project_id=? WHERE id=?", (project["id"], task_id)
        )
        con.commit()
    finally:
        con.close()

    core.time_entry_start(
        tenant_id="TENANT_A",
        user="alice",
        project_id=project["id"],
        task_id=task_id,
        started_at="2026-02-01T10:00:00",
    )
    core.time_entry_stop(
        tenant_id="TENANT_A",
        user="alice",
        ended_at="2026-02-01T12:00:00",
    )

    customer_id = core.customers_create("TENANT_A", "Quote Kunde")
    deal_id = core.deals_create(
        tenant_id="TENANT_A",
        customer_id=customer_id,
        title="Deal mit Zeiten",
        stage="proposal",
        value_cents=50000,
        project_id=project["id"],
    )

    quote = core.quotes_create_from_deal("TENANT_A", deal_id)
    assert quote["deal_id"] == deal_id
    assert quote["total_cents"] > 0
    assert quote["items"]

    assert _count_events(core.DB_PATH, "crm_quote") >= 2
    assert _count_events(core.DB_PATH, "crm_quote_item") >= 1
