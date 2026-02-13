from __future__ import annotations

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


def test_api_tenant_isolation_customers(tmp_path: Path) -> None:
    _init_core(tmp_path)
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    client = app.test_client()

    with client.session_transaction() as sess:
        sess["user"] = "alice"
        sess["role"] = "ADMIN"
        sess["tenant_id"] = "TENANT_A"
    res_create = client.post("/api/customers", json={"name": "A-Customer"})
    assert res_create.status_code == 200
    customer_id = (res_create.get_json() or {}).get("customer", {}).get("id")
    assert customer_id

    with client.session_transaction() as sess:
        sess["user"] = "bob"
        sess["role"] = "ADMIN"
        sess["tenant_id"] = "TENANT_B"
    res_get = client.get(f"/api/customers/{customer_id}")
    assert res_get.status_code == 404
    payload = res_get.get_json() or {}
    assert payload.get("error", {}).get("code") == "not_found"
