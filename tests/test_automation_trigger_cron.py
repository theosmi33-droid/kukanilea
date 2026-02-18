from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import kukanilea_core_v3_fixed as core
from app.automation.cron import cron_match
from app.automation.runner import process_cron_for_tenant
from app.automation.store import create_rule, list_execution_logs


def _set_core_db(tmp_path: Path, monkeypatch) -> Path:
    db_path = tmp_path / "core.sqlite3"
    monkeypatch.setattr(core, "DB_PATH", db_path)
    return db_path


def test_cron_match_supports_wildcards_and_fixed_values() -> None:
    dt = datetime(2026, 2, 18, 8, 30, tzinfo=timezone.utc)  # Wednesday => 3
    assert cron_match("* * * * *", dt) is True
    assert cron_match("30 8 * * 3", dt) is True
    assert cron_match("31 8 * * 3", dt) is False
    assert cron_match("30 9 * * 3", dt) is False


def test_cron_match_rejects_invalid_expression() -> None:
    dt = datetime(2026, 2, 18, 8, 30, tzinfo=timezone.utc)
    try:
        cron_match("*/5 8 * * *", dt)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for unsupported cron syntax")


def test_cron_trigger_executes_once_per_minute(tmp_path: Path, monkeypatch) -> None:
    db_path = _set_core_db(tmp_path, monkeypatch)
    calls: list[int] = []

    def _task_create(**_kwargs):
        calls.append(1)
        return 100 + len(calls)

    monkeypatch.setattr(core, "task_create", _task_create)

    rule_id = create_rule(
        tenant_id="TENANT_A",
        name="Cron task",
        triggers=[{"trigger_type": "cron", "config": {"cron": "30 8 * * 3"}}],
        conditions=[],
        actions=[{"action_type": "create_task", "config": {"requires_confirm": False}}],
        db_path=db_path,
    )
    tick = datetime(2026, 2, 18, 8, 30, tzinfo=timezone.utc)
    first = process_cron_for_tenant("TENANT_A", db_path=db_path, now_dt=tick)
    assert first["ok"] is True
    assert int(first["matched"]) == 1
    assert len(calls) == 1

    second = process_cron_for_tenant("TENANT_A", db_path=db_path, now_dt=tick)
    assert second["ok"] is True
    assert int(second["matched"]) == 1
    assert len(calls) == 1

    logs = list_execution_logs(tenant_id="TENANT_A", rule_id=rule_id, db_path=db_path)
    assert any(str(row["trigger_type"]) == "cron" for row in logs)


def test_cron_trigger_ignores_non_matching_minute(tmp_path: Path, monkeypatch) -> None:
    db_path = _set_core_db(tmp_path, monkeypatch)
    create_rule(
        tenant_id="TENANT_A",
        name="Cron miss",
        triggers=[{"trigger_type": "cron", "config": {"cron": "30 8 * * 3"}}],
        conditions=[],
        actions=[],
        db_path=db_path,
    )
    tick = datetime(2026, 2, 18, 8, 31, tzinfo=timezone.utc)
    result = process_cron_for_tenant("TENANT_A", db_path=db_path, now_dt=tick)
    assert result["ok"] is True
    assert int(result["matched"]) == 0
