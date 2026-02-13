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


def test_retry_on_locked_db(monkeypatch, tmp_path: Path) -> None:
    _init_core(tmp_path)

    original_db = core._db
    state = {"remaining": 2}

    class WrappedConn:
        def __init__(self, inner):
            self._inner = inner

        def execute(self, sql, params=()):
            if sql == "BEGIN IMMEDIATE" and state["remaining"] > 0:
                state["remaining"] -= 1
                raise sqlite3.OperationalError("database is locked")
            return self._inner.execute(sql, params)

        def __getattr__(self, item):
            return getattr(self._inner, item)

    def _patched_db():
        return WrappedConn(original_db())

    monkeypatch.setattr(core, "_db", _patched_db)
    cid = core.customers_create("TENANT_A", "Retry AG")
    assert cid
    assert state["remaining"] == 0
