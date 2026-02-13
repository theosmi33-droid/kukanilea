from __future__ import annotations

import sqlite3
from pathlib import Path

import kukanilea_core_v3_fixed as core
from app import create_app


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


def test_customers_tenant_isolation_and_event(tmp_path: Path) -> None:
    _init_core(tmp_path)

    c1 = core.customers_create("TENANT_A", "Acme A")
    core.customers_create("TENANT_B", "Acme B")

    list_a = core.customers_list("TENANT_A")
    list_b = core.customers_list("TENANT_B")

    assert len(list_a) == 1
    assert list_a[0]["id"] == c1
    assert len(list_b) == 1
    assert list_b[0]["id"] != c1
    assert _count_events(core.DB_PATH, "crm_customer") == 2


def test_read_only_blocks_crm_mutation_route(tmp_path: Path) -> None:
    _init_core(tmp_path)
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test", READ_ONLY=True)

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user"] = "dev"
        sess["role"] = "ADMIN"
        sess["tenant_id"] = "TENANT_A"

    resp = client.post("/api/customers", json={"name": "Blocked"})
    assert resp.status_code == 403
    payload = resp.get_json() or {}
    assert payload.get("error", {}).get("code") == "read_only"
