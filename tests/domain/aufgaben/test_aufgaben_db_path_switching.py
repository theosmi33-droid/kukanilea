from __future__ import annotations

import sqlite3

from app.core import logic as core_logic
from app.modules.aufgaben import logic as aufgaben_logic


def test_aufgaben_respects_runtime_tenant_db_switch(tmp_path, monkeypatch):
    tenant_a_db = tmp_path / "tenant_a.sqlite3"
    tenant_b_db = tmp_path / "tenant_b.sqlite3"

    monkeypatch.setattr(core_logic, "DB_PATH", str(tenant_a_db))
    first = aufgaben_logic.create_task(
        tenant="TENANT_A",
        title="Tenant A task",
        created_by="tester-a",
    )
    assert first.get("tenant") == "TENANT_A"

    monkeypatch.setattr(core_logic, "DB_PATH", str(tenant_b_db))
    second = aufgaben_logic.create_task(
        tenant="TENANT_B",
        title="Tenant B task",
        created_by="tester-b",
    )
    assert second.get("tenant") == "TENANT_B"

    con_a = sqlite3.connect(tenant_a_db)
    try:
        rows_a = con_a.execute("SELECT tenant, title FROM aufgaben_tasks ORDER BY id").fetchall()
    finally:
        con_a.close()

    con_b = sqlite3.connect(tenant_b_db)
    try:
        rows_b = con_b.execute("SELECT tenant, title FROM aufgaben_tasks ORDER BY id").fetchall()
    finally:
        con_b.close()

    assert rows_a == [("TENANT_A", "Tenant A task")]
    assert rows_b == [("TENANT_B", "Tenant B task")]
