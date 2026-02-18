from __future__ import annotations

import sqlite3
from pathlib import Path

from app.automation.store import (
    ACTION_TABLE,
    CONDITION_TABLE,
    TRIGGER_TABLE,
    create_rule,
    delete_rule,
    get_rule,
    list_rules,
    update_rule,
)


def _connect(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(db_path), timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON;")
    return con


def test_automation_store_minimal_crud_and_tenant_isolation(tmp_path: Path) -> None:
    db_path = tmp_path / "core.sqlite3"
    tenant_a = "TENANT_A"
    tenant_b = "TENANT_B"

    rule_id = create_rule(
        tenant_id=tenant_a,
        name="Lead from Inbox",
        description="Create lead when inbox trigger matches",
        is_enabled=True,
        triggers=[
            {"trigger_type": "eventlog", "config": {"event_type": "mail.received"}}
        ],
        conditions=[
            {
                "condition_type": "field_match",
                "config": {"path": "channel", "eq": "email"},
            }
        ],
        actions=[
            {"action_type": "create_lead", "config": {"owner": "sales"}},
            {"action_type": "create_task", "config": {"due_in_days": 2}},
        ],
        db_path=db_path,
    )

    loaded = get_rule(tenant_id=tenant_a, rule_id=rule_id, db_path=db_path)
    assert loaded is not None
    assert loaded["id"] == rule_id
    assert loaded["name"] == "Lead from Inbox"
    assert loaded["is_enabled"] is True
    assert loaded["max_executions_per_minute"] == 10
    assert loaded["version"] == 1
    assert len(loaded["triggers"]) == 1
    assert len(loaded["conditions"]) == 1
    assert len(loaded["actions"]) == 2
    assert loaded["triggers"][0]["config"]["event_type"] == "mail.received"

    listing = list_rules(tenant_id=tenant_a, db_path=db_path)
    assert len(listing) == 1
    assert listing[0]["id"] == rule_id
    assert listing[0]["action_count"] == 2
    assert listing[0]["max_executions_per_minute"] == 10

    updated = update_rule(
        tenant_id=tenant_a,
        rule_id=rule_id,
        patch={
            "name": "Lead + Followup",
            "description": "Updated",
            "is_enabled": False,
            "max_executions_per_minute": 3,
            "triggers": [
                {
                    "type": "manual",
                    "config_json": '{"source":"operator","priority":"high"}',
                }
            ],
            "actions": [{"action_type": "create_followup", "config": {"owner": "ops"}}],
        },
        db_path=db_path,
    )
    assert updated is not None
    assert updated["name"] == "Lead + Followup"
    assert updated["description"] == "Updated"
    assert updated["is_enabled"] is False
    assert updated["max_executions_per_minute"] == 3
    assert updated["version"] == 2
    assert len(updated["triggers"]) == 1
    assert updated["triggers"][0]["type"] == "manual"
    assert updated["triggers"][0]["config"]["priority"] == "high"
    assert len(updated["actions"]) == 1

    assert get_rule(tenant_id=tenant_b, rule_id=rule_id, db_path=db_path) is None
    assert list_rules(tenant_id=tenant_b, db_path=db_path) == []
    assert delete_rule(tenant_id=tenant_b, rule_id=rule_id, db_path=db_path) is False
    assert delete_rule(tenant_id=tenant_a, rule_id=rule_id, db_path=db_path) is True
    assert get_rule(tenant_id=tenant_a, rule_id=rule_id, db_path=db_path) is None

    con = _connect(db_path)
    try:
        trigger_count = int(
            con.execute(f"SELECT COUNT(1) AS c FROM {TRIGGER_TABLE}").fetchone()["c"]
        )
        condition_count = int(
            con.execute(f"SELECT COUNT(1) AS c FROM {CONDITION_TABLE}").fetchone()["c"]
        )
        action_count = int(
            con.execute(f"SELECT COUNT(1) AS c FROM {ACTION_TABLE}").fetchone()["c"]
        )
        assert trigger_count == 0
        assert condition_count == 0
        assert action_count == 0
    finally:
        con.close()
