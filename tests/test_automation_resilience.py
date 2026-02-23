from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

import kukanilea_core_v3_fixed as core
from app.automation.runner import LoopGuardError, process_events_for_tenant
from app.automation.store import (
    EXECUTION_LOG_TABLE,
    create_rule,
    ensure_automation_schema,
)
from app.config import Config
from app.eventlog.core import event_append


def _init_core(tmp_path: Path) -> None:
    core.DB_PATH = tmp_path / "core.db"
    Config.CORE_DB = str(core.DB_PATH)
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()
    ensure_automation_schema(core.DB_PATH)


def test_loop_guard_raises_error(tmp_path: Path) -> None:
    _init_core(tmp_path)
    
    tenant_id = "TENANT_LOOP"
    
    # Create a rule that triggers on 'test_event'
    # We set max_executions_per_minute=5
    create_rule(
        tenant_id=tenant_id,
        name="Loop Rule",
        max_executions_per_minute=5,
        triggers=[{"type": "eventlog", "config": {"allowed_event_types": ["test_event"]}}],
        actions=[{"type": "create_task", "config": {"title": "Loop Task", "requires_confirm": False}}],
        db_path=core.DB_PATH
    )

    # Inject 10 events
    for i in range(10):
        con = sqlite3.connect(str(core.DB_PATH))
        con.row_factory = sqlite3.Row
        event_append(
            event_type="test_event",
            entity_type="lead",
            entity_id=i+1,
            payload={"tenant_id": tenant_id},
            con=con
        )
        con.commit()
        con.close()

    # The first 5 should pass, the 6th should raise LoopGuardError
    with pytest.raises(LoopGuardError):
        process_events_for_tenant(tenant_id, limit=20, db_path=core.DB_PATH)
    
    # Verify log contains loop_detected
    con = sqlite3.connect(str(core.DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        logs = con.execute(f"SELECT status FROM {EXECUTION_LOG_TABLE} WHERE tenant_id=?", (tenant_id,)).fetchall()
        statuses = [row["status"] for row in logs]
        assert "loop_detected" in statuses
        # Should have 5 successful/pending ones and at least 1 loop_detected
        assert len(statuses) >= 6
    finally:
        con.close()


def test_dry_run_skips_mutation(tmp_path: Path) -> None:
    _init_core(tmp_path)
    tenant_id = "TENANT_DRY"
    
    rule_id = create_rule(
        tenant_id=tenant_id,
        name="Dry Rule",
        triggers=[{"type": "eventlog", "config": {"allowed_event_types": ["dry_event"]}}],
        actions=[{"type": "create_task", "config": {"title": "Dry Task", "requires_confirm": False}}],
        db_path=core.DB_PATH
    )

    con = sqlite3.connect(str(core.DB_PATH))
    con.row_factory = sqlite3.Row
    event_append(
        event_type="dry_event",
        entity_type="lead",
        entity_id=1,
        payload={"tenant_id": tenant_id},
        con=con
    )
    con.commit()
    con.close()

    # Manual execution with dry_run using simulate_rule_for_tenant (which uses dry_run=True)
    from app.automation.runner import simulate_rule_for_tenant
    
    result = simulate_rule_for_tenant(tenant_id, rule_id, db_path=core.DB_PATH)
    
    assert result["ok"] is True
    # If requires_confirm is False, it should be 'executed'
    assert result["result"]["executed"] == 1 or result["result"]["pending"] == 1
    
    # Verify NO task was actually created
    con = sqlite3.connect(str(core.DB_PATH))
    count = con.execute("SELECT COUNT(*) FROM tasks WHERE tenant=?", (tenant_id,)).fetchone()[0]
    con.close()
    assert count == 0
