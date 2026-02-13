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


def test_deals_create_list_and_stage_update(tmp_path: Path) -> None:
    _init_core(tmp_path)
    customer_id = core.customers_create("TENANT_A", "Deal Kunde")

    deal_id = core.deals_create(
        tenant_id="TENANT_A",
        customer_id=customer_id,
        title="Neue Chance",
        stage="lead",
        value_cents=125000,
    )
    deals = core.deals_list("TENANT_A", stage="lead")
    assert any(d["id"] == deal_id for d in deals)

    updated = core.deals_update_stage("TENANT_A", deal_id, "qualified")
    assert updated["stage"] == "qualified"

    assert _count_events(core.DB_PATH, "crm_deal") == 2
