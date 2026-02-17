from __future__ import annotations

from pathlib import Path

from app.automation.store import get_state_cursor, upsert_state_cursor


def test_automation_state_cursor_roundtrip(tmp_path: Path) -> None:
    db_path = tmp_path / "core.sqlite3"
    assert (
        get_state_cursor(tenant_id="TENANT_A", source="eventlog", db_path=db_path) == ""
    )
    upsert_state_cursor(
        tenant_id="TENANT_A",
        source="eventlog",
        cursor="42",
        db_path=db_path,
    )
    assert (
        get_state_cursor(tenant_id="TENANT_A", source="eventlog", db_path=db_path)
        == "42"
    )
    upsert_state_cursor(
        tenant_id="TENANT_A",
        source="eventlog",
        cursor="43",
        db_path=db_path,
    )
    assert (
        get_state_cursor(tenant_id="TENANT_A", source="eventlog", db_path=db_path)
        == "43"
    )


def test_automation_state_cursor_tenant_isolated(tmp_path: Path) -> None:
    db_path = tmp_path / "core.sqlite3"
    upsert_state_cursor(
        tenant_id="TENANT_A",
        source="eventlog",
        cursor="7",
        db_path=db_path,
    )
    assert (
        get_state_cursor(tenant_id="TENANT_B", source="eventlog", db_path=db_path) == ""
    )
