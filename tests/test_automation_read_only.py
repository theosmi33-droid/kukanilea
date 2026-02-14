from __future__ import annotations

import sqlite3
from pathlib import Path

import kukanilea_core_v3_fixed as core
from app import create_app
from app.automation.core import automation_rule_create


def _init_core(tmp_path: Path) -> None:
    core.DB_PATH = tmp_path / "core.db"
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()


def test_run_now_blocked_in_read_only(tmp_path: Path) -> None:
    _init_core(tmp_path)
    automation_rule_create(
        "TENANT_A",
        "r1",
        "leads",
        "lead_screening_stale",
        '{"hours_in_screening":1}',
        '[{"kind":"lead_pin","value":true}]',
        "dev",
    )

    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test", READ_ONLY=True)
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user"] = "dev"
        sess["role"] = "OPERATOR"
        sess["tenant_id"] = "TENANT_A"

    r = client.post("/api/automation/run-now", json={"max_actions": 5})
    assert r.status_code == 403

    con = sqlite3.connect(str(core.DB_PATH))
    try:
        c = con.execute("SELECT COUNT(*) FROM automation_runs").fetchone()
        assert int(c[0] if c else 0) == 0
    finally:
        con.close()
