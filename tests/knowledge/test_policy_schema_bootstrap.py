from __future__ import annotations

import sqlite3

from app.knowledge import core as knowledge_core


def test_knowledge_policy_get_bootstraps_missing_policy_table(tmp_path, monkeypatch):
    db_path = tmp_path / "core.sqlite3"

    def _run_write_txn(fn):
        con = sqlite3.connect(db_path)
        con.row_factory = sqlite3.Row
        try:
            result = fn(con)
            con.commit()
            return result
        finally:
            con.close()

    monkeypatch.setattr(
        knowledge_core.legacy_core, "_run_write_txn", _run_write_txn, raising=False
    )
    monkeypatch.setattr(
        knowledge_core.legacy_core,
        "_effective_tenant",
        lambda tenant: tenant or "KUKANILEA",
        raising=False,
    )
    monkeypatch.setattr(
        knowledge_core.legacy_core, "TENANT_DEFAULT", "KUKANILEA", raising=False
    )

    row = knowledge_core.knowledge_policy_get("KUKANILEA")

    assert row["tenant_id"] == "KUKANILEA"
    assert int(row["allow_calendar"]) == 0
    with sqlite3.connect(db_path) as con:
        table = con.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='table' AND name='knowledge_source_policies'
            """
        ).fetchone()
        assert table is not None
