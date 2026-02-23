from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path

from flask import Flask

import kukanilea_core_v3_fixed as core
from app.autonomy.maintenance import run_backup, verify_backup
from app.config import Config


def _init_core(tmp_path: Path) -> None:
    core.DB_PATH = tmp_path / "core.db"
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()
    Config.CORE_DB = str(core.DB_PATH)


def test_backup_create_rotate_and_verify(tmp_path: Path, monkeypatch) -> None:
    _init_core(tmp_path)
    backup_root = tmp_path / "backups"
    backup_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("KUKANILEA_BACKUP_DIR", str(backup_root))

    tenant_dir = backup_root / "TENANT_A"
    tenant_dir.mkdir(parents=True, exist_ok=True)
    old_file = tenant_dir / "backup-old.sqlite"
    old_file.write_bytes(b"old")
    old_ts = time.time() - (10 * 24 * 3600)
    os.utime(old_file, (old_ts, old_ts))

    result = run_backup("TENANT_A", actor_user_id="dev", rotate=True)
    assert result["ok"] is True
    assert result["backup_name"].startswith("backup-")
    backup_fp = tenant_dir / str(result["backup_name"])
    assert backup_fp.exists()
    assert verify_backup(backup_fp) is True
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
        payload = str(row["payload_json"] or "")
        assert str(backup_root) not in payload
    finally:
        con.close()


def test_backup_read_only_blocks_file_ops(tmp_path: Path, monkeypatch) -> None:
    _init_core(tmp_path)
    backup_root = tmp_path / "backups"
    backup_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("KUKANILEA_BACKUP_DIR", str(backup_root))

    app = Flask(__name__)
    app.config["READ_ONLY"] = True
    with app.app_context():
        result = run_backup("TENANT_A", actor_user_id="dev", rotate=True)
    assert result["ok"] is False
    assert result["skipped"] == "read_only"
    assert not (backup_root / "TENANT_A").exists()
