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


def test_max_actions_aborts_run(tmp_path: Path) -> None:
    _init_core(tmp_path)

    for i in range(40):
        leads_create(
            tenant_id="TENANT_A",
            source="manual",
            contact_name=f"A{i}",
            contact_email=f"a{i}@example.com",
            contact_phone="",
            subject=f"S{i}",
            message="M",
        )

    # make screening leads stale so the condition matches deterministically
    con0 = sqlite3.connect(str(core.DB_PATH))
    try:
        con0.execute("UPDATE leads SET created_at=datetime('now','-2 hour')")
        con0.commit()
    finally:
        con0.close()

    automation_rule_create(
        "TENANT_A",
        "r1",
        "leads",
        "lead_screening_stale",
        '{"hours_in_screening":1}',
        '[{"kind":"lead_pin","value":true},{"kind":"lead_set_priority","value":"high"}]',
        "dev",
    )

    run_id = automation_run_now("TENANT_A", "dev", max_actions=3)

    con = sqlite3.connect(str(core.DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        run = con.execute(
            "SELECT status, actions_executed, aborted_reason FROM automation_runs WHERE id=?",
            (run_id,),
        ).fetchone()
        assert run is not None
        assert run["status"] == "aborted"
        assert int(run["actions_executed"]) == 3
        assert run["aborted_reason"] == "max_actions"

        count = con.execute(
            "SELECT COUNT(*) FROM automation_run_actions WHERE run_id=?",
            (run_id,),
        ).fetchone()
        assert int(count[0]) <= 3
    finally:
        con.close()
