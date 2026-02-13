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


def test_read_only_crm_endpoints_do_not_write(tmp_path: Path) -> None:
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

    con = sqlite3.connect(str(core.DB_PATH))
    try:
        row = con.execute("SELECT COUNT(*) FROM customers").fetchone()
        assert int(row[0] if row else 0) == 0
    finally:
        con.close()
