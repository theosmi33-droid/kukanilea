from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path

import kukanilea_core_v3_fixed as core
from app.autonomy.maintenance import run_backup_once


def _init_core(tmp_path: Path) -> None:
    core.DB_PATH = tmp_path / "core.db"
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()


def test_backup_creates_and_rotates(tmp_path: Path, monkeypatch) -> None:
    _init_core(tmp_path)

    backup_dir = tmp_path / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("KUKANILEA_BACKUP_DIR", str(backup_dir))
    monkeypatch.setenv("KUKANILEA_BACKUP_KEEP_DAYS", "1")

    old_file = backup_dir / "old.sqlite3"
    old_file.write_bytes(b"old")
    old_ts = time.time() - (3 * 24 * 3600)
    os.utime(old_file, (old_ts, old_ts))

    result = run_backup_once(tenant_id="TENANT_A", actor_user_id="dev", rotate=True)
    assert result["ok"] is True
    assert result["backup_name"].startswith("TENANT_A-")

    backup_file = backup_dir / str(result["backup_name"])
    assert backup_file.exists()
    assert old_file.name in result["rotated"]
    assert not old_file.exists()

    con = sqlite3.connect(str(core.DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            """
            SELECT event_type, payload_json
            FROM events
            WHERE event_type='maintenance_backup_ok'
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
        assert row is not None
        payload = str(row["payload_json"])
        assert "old.sqlite3" not in payload
        assert str(backup_dir) not in payload
    finally:
        con.close()
