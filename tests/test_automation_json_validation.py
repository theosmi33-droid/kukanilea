from __future__ import annotations

import sqlite3
from pathlib import Path

import kukanilea_core_v3_fixed as core
from app.automation.core import automation_rule_create, automation_run_now


def _init_core(tmp_path: Path) -> None:
    core.DB_PATH = tmp_path / "core.db"
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()


def test_oversize_json_rejected(tmp_path: Path) -> None:
    _init_core(tmp_path)
    huge = "{" + '"a":' + '"' + ("x" * (40 * 1024)) + '"}'
    try:
        automation_rule_create(
            "TENANT_A",
            "big",
            "leads",
            "lead_overdue",
            huge,
            '[{"kind":"lead_pin","value":true}]',
            "dev",
        )
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")


def test_invalid_json_disables_rule_on_run(tmp_path: Path) -> None:
    _init_core(tmp_path)
    rule_id = automation_rule_create(
        "TENANT_A",
        "r1",
        "leads",
        "lead_overdue",
        '{"days_overdue":0,"status_in":["new"],"priority_in":["normal"]}',
        '[{"kind":"lead_pin","value":true}]',
        "dev",
    )

    con = sqlite3.connect(str(core.DB_PATH))
    try:
        con.execute(
            "UPDATE automation_rules SET condition_json=? WHERE id=?",
            ("{invalid", rule_id),
        )
        con.commit()
    finally:
        con.close()

    run_id = automation_run_now("TENANT_A", "dev", max_actions=5)
    assert run_id

    con = sqlite3.connect(str(core.DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            "SELECT enabled, last_error FROM automation_rules WHERE id=?",
            (rule_id,),
        ).fetchone()
        assert row is not None
        assert int(row["enabled"]) == 0
        assert row["last_error"]
    finally:
        con.close()


def test_unknown_condition_kind_rejected(tmp_path: Path) -> None:
    _init_core(tmp_path)
    try:
        automation_rule_create(
            "TENANT_A",
            "bad",
            "leads",
            "unknown_kind",
            "{}",
            '[{"kind":"lead_pin","value":true}]',
            "dev",
        )
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")
