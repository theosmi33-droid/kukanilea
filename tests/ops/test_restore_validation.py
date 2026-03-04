from __future__ import annotations

import sqlite3
from pathlib import Path

from scripts.ops.restore_validation import collect_snapshot, compare_snapshots


def _make_db(path: Path, tenant: str = "DEMO_TENANT") -> None:
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE contacts(id TEXT, tenant_id TEXT, full_name TEXT);
        CREATE TABLE tasks(id TEXT, tenant_id TEXT, title TEXT);
        CREATE TABLE projects(id TEXT, tenant_id TEXT, name TEXT);
        CREATE TABLE time_entries(id TEXT, tenant_id TEXT, minutes INTEGER);
        CREATE TABLE files(id TEXT, tenant_id TEXT, name TEXT);
        """
    )
    for table in ["contacts", "tasks", "projects", "time_entries", "files"]:
        con.execute(f"INSERT INTO {table}(id, tenant_id) VALUES(?, ?)", (f"{table}_1", tenant))
    con.commit()
    con.close()


def test_collect_snapshot_counts_and_hashes(tmp_path: Path) -> None:
    db = tmp_path / "db.sqlite3"
    _make_db(db)
    snap = collect_snapshot(db, "DEMO_TENANT")
    assert snap["contacts"]["count"] == 1
    assert len(snap["files"]["sample_hash"]) == 64


def test_compare_snapshots_detects_mismatch(tmp_path: Path) -> None:
    db = tmp_path / "db.sqlite3"
    _make_db(db)
    before = collect_snapshot(db, "DEMO_TENANT")
    con = sqlite3.connect(db)
    con.execute("INSERT INTO contacts(id, tenant_id, full_name) VALUES('c2','DEMO_TENANT','x')")
    con.commit()
    con.close()
    after = collect_snapshot(db, "DEMO_TENANT")
    ok, issues = compare_snapshots(before, after)
    assert ok is False
    assert any("contacts" in issue for issue in issues)


def test_compare_snapshots_ok_when_same(tmp_path: Path) -> None:
    db = tmp_path / "db.sqlite3"
    _make_db(db)
    before = collect_snapshot(db, "DEMO_TENANT")
    after = collect_snapshot(db, "DEMO_TENANT")
    ok, issues = compare_snapshots(before, after)
    assert ok is True
    assert issues == []
