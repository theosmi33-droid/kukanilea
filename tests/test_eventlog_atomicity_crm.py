from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

import kukanilea_core_v3_fixed as core


def _init_core(tmp_path: Path) -> None:
    core.DB_PATH = tmp_path / "core.db"
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()


def test_customer_create_rolls_back_when_event_fails(
    monkeypatch, tmp_path: Path
) -> None:
    _init_core(tmp_path)

    def _boom(*args, **kwargs):
        raise RuntimeError("event_fail")

    monkeypatch.setattr(core, "event_append", _boom)

    with pytest.raises(RuntimeError):
        core.customers_create("TENANT_A", "Rollback GmbH")

    con = sqlite3.connect(str(core.DB_PATH))
    try:
        row = con.execute("SELECT COUNT(*) FROM customers").fetchone()
        assert int(row[0] if row else 0) == 0
    finally:
        con.close()
