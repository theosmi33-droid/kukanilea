from __future__ import annotations

import sqlite3
from pathlib import Path

from app.devtools.schema_audit import analyze_db


def _make_db(path: Path) -> None:
    con = sqlite3.connect(str(path))
    try:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS demo_items(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              tenant_id TEXT NOT NULL,
              name TEXT NOT NULL
            )
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS auth_outbox(
              id TEXT PRIMARY KEY,
              tenant_id TEXT NOT NULL,
              kind TEXT NOT NULL
            )
            """
        )
        con.commit()
    finally:
        con.close()


def test_analyze_db_detects_non_text_ids(tmp_path: Path) -> None:
    db_path = tmp_path / "core.sqlite3"
    _make_db(db_path)

    report = analyze_db(db_path)
    assert report["ok"] is False
    findings = report["findings"]
    assert any(f["code"] == "autoincrement_pk" for f in findings)
    assert any(f["code"] == "id_not_text_pk" for f in findings)
    assert not any(
        f["code"] == "missing_tenant_id" and f["table"] == "demo_items"
        for f in findings
    )


def test_analyze_db_handles_missing_file(tmp_path: Path) -> None:
    report = analyze_db(tmp_path / "missing.sqlite3")
    assert report["ok"] is False
    assert report["findings"][0]["code"] == "db_missing"
