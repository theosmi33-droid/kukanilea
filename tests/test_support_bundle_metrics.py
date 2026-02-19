from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import kukanilea_core_v3_fixed as core
from app.demo_data import seed_demo_dataset
from app.devtools.support_bundle import collect_pilot_metrics


def _init_core(tmp_path: Path) -> Path:
    db_path = tmp_path / "core.db"
    core.DB_PATH = db_path
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()
    return db_path


def test_collect_pilot_metrics_empty_tenant(tmp_path: Path) -> None:
    db_path = _init_core(tmp_path)
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        metrics = collect_pilot_metrics(con, "DEMO_AG")
    finally:
        con.close()

    assert metrics["tenant_id"] == "DEMO_AG"
    assert int(metrics["logins_last_14d"]) == 0
    assert int(metrics["documents_total"]) == 0
    assert int(metrics["tasks_total"]) == 0
    assert int(metrics["automation_executions"]) == 0
    assert int(metrics["active_rules"]) == 0
    assert metrics["last_activity"] is None


def test_collect_pilot_metrics_after_demo_seed(tmp_path: Path, monkeypatch) -> None:
    db_path = _init_core(tmp_path)
    auth_path = tmp_path / "auth.sqlite3"
    docs_path = tmp_path / "docs"
    monkeypatch.setenv("KUKANILEA_ANONYMIZATION_KEY", "seed-test-anon")

    seed_demo_dataset(
        db_path=db_path,
        auth_db_path=auth_path,
        tenant_id="DEMO_AG",
        tenant_name="DEMO AG",
        create_auth_user=True,
        documents_root=docs_path,
    )

    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        metrics = collect_pilot_metrics(con, "DEMO_AG")
    finally:
        con.close()

    assert int(metrics["documents_total"]) == 10
    assert int(metrics["tasks_total"]) == 3
    assert int(metrics["active_rules"]) == 1
    assert int(metrics["automation_executions"]) == 0

    serialized = json.dumps(metrics, sort_keys=True)
    assert "@demo.invalid" not in serialized
    assert "Max Mustermann" not in serialized
