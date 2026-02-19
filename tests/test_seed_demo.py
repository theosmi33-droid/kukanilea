from __future__ import annotations

import sqlite3
from pathlib import Path

import kukanilea_core_v3_fixed as core
from app.demo_data import seed_demo_dataset


def _init_core(tmp_path: Path) -> Path:
    db_path = tmp_path / "core.db"
    core.DB_PATH = db_path
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()
    return db_path


def _count_table(db_path: Path, sql: str, params: tuple[str, ...]) -> int:
    con = sqlite3.connect(str(db_path))
    try:
        row = con.execute(sql, params).fetchone()
        return int(row[0] if row else 0)
    finally:
        con.close()


def test_seed_demo_dataset_is_idempotent(tmp_path: Path, monkeypatch) -> None:
    db_path = _init_core(tmp_path)
    auth_path = tmp_path / "auth.sqlite3"
    docs_path = tmp_path / "demo_docs"
    monkeypatch.setenv("KUKANILEA_ANONYMIZATION_KEY", "seed-test-anon")

    first = seed_demo_dataset(
        db_path=db_path,
        auth_db_path=auth_path,
        tenant_id="DEMO_AG",
        tenant_name="DEMO AG",
        create_auth_user=True,
        documents_root=docs_path,
    )
    second = seed_demo_dataset(
        db_path=db_path,
        auth_db_path=auth_path,
        tenant_id="DEMO_AG",
        tenant_name="DEMO AG",
        create_auth_user=True,
        documents_root=docs_path,
    )

    assert int(first["customers"]) == 5
    assert int(first["contacts"]) == 5
    assert int(first["tasks"]) == 3
    assert int(first["documents"]) == 10
    assert int(first["automation_rules"]) == 1

    assert int(second["customers"]) == 5
    assert int(second["contacts"]) == 5
    assert int(second["tasks"]) == 3
    assert int(second["documents"]) == 10
    assert int(second["automation_rules"]) == 1

    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        emails = [
            str(r["email"] or "")
            for r in con.execute(
                "SELECT email FROM contacts WHERE tenant_id='DEMO_AG' ORDER BY email"
            ).fetchall()
        ]
    finally:
        con.close()

    assert len(emails) == 5
    assert all(addr.endswith("@demo.invalid") for addr in emails)


def test_seed_demo_dataset_force_recreates_fixture(tmp_path: Path, monkeypatch) -> None:
    db_path = _init_core(tmp_path)
    auth_path = tmp_path / "auth.sqlite3"
    docs_path = tmp_path / "demo_docs"
    monkeypatch.setenv("KUKANILEA_ANONYMIZATION_KEY", "seed-test-anon")

    seed_demo_dataset(
        db_path=db_path,
        auth_db_path=auth_path,
        tenant_id="DEMO_AG",
        tenant_name="DEMO AG",
        create_auth_user=True,
        documents_root=docs_path,
    )

    core.customers_create(
        tenant_id="DEMO_AG",
        name="Extra Kunde fuer Force Test",
        notes="temporary",
    )
    assert (
        _count_table(
            db_path,
            "SELECT COUNT(*) FROM customers WHERE tenant_id=?",
            ("DEMO_AG",),
        )
        == 6
    )

    summary = seed_demo_dataset(
        db_path=db_path,
        auth_db_path=auth_path,
        tenant_id="DEMO_AG",
        tenant_name="DEMO AG",
        create_auth_user=True,
        documents_root=docs_path,
        force=True,
    )

    assert int(summary["customers"]) == 5
    assert int(summary["contacts"]) == 5
    assert int(summary["tasks"]) == 3
    assert int(summary["documents"]) == 10
    assert int(summary["automation_rules"]) == 1
