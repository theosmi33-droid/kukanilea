from __future__ import annotations

import sqlite3
from pathlib import Path

import kukanilea_core_v3_fixed as core
from app.automation.core import automation_rule_create, automation_run_now
from app.lead_intake.core import leads_create


def _init_core(tmp_path: Path) -> None:
    core.DB_PATH = tmp_path / "core.db"
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()


def test_automation_does_not_cross_tenants(tmp_path: Path) -> None:
    _init_core(tmp_path)

    lead_a = leads_create("TENANT_A", "manual", "A", "a@example.com", "", "SA", "M")
    lead_b = leads_create("TENANT_B", "manual", "B", "b@example.com", "", "SB", "M")

    con0 = sqlite3.connect(str(core.DB_PATH))
    try:
        con0.execute(
            "UPDATE leads SET created_at=datetime('now','-2 hour') WHERE tenant_id='TENANT_A'"
        )
        con0.commit()
    finally:
        con0.close()

    automation_rule_create(
        "TENANT_A",
        "rA",
        "leads",
        "lead_screening_stale",
        '{"hours_in_screening":1}',
        '[{"kind":"lead_pin","value":true}]',
        "dev",
    )

    automation_run_now("TENANT_A", "dev", max_actions=20)

    con = sqlite3.connect(str(core.DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        a = con.execute(
            "SELECT pinned FROM leads WHERE tenant_id='TENANT_A' AND id=?", (lead_a,)
        ).fetchone()
        b = con.execute(
            "SELECT pinned FROM leads WHERE tenant_id='TENANT_B' AND id=?", (lead_b,)
        ).fetchone()
        assert a is not None and int(a["pinned"] or 0) == 1
        assert b is not None and int(b["pinned"] or 0) == 0
    finally:
        con.close()
