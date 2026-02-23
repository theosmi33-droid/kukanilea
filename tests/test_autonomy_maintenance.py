from __future__ import annotations

import sqlite3
from pathlib import Path

import kukanilea_core_v3_fixed as core
from app.autonomy.maintenance import run_backup_once
from app.config import Config


def _init_core(tmp_path: Path) -> None:
    core.DB_PATH = tmp_path / "core.db"
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()
    Config.CORE_DB = str(core.DB_PATH)


def test_run_backup_once_creates_backup_and_event(tmp_path: Path, monkeypatch) -> None:
    _init_core(tmp_path)
    backup_root = tmp_path / "backups"
    monkeypatch.setenv("KUKANILEA_BACKUP_DIR", str(backup_root))

    result = run_backup_once(tenant_id="TENANT_A", actor_user_id="dev")
    assert result["ok"] is True
    tenant_dir = backup_root / "TENANT_A"
    assert tenant_dir.exists()
    assert (tenant_dir / str(result["backup_name"])).exists()

    con = sqlite3.connect(str(core.DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            """
            SELECT event_type
            FROM events
            WHERE event_type='maintenance_backup_ok'
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
        assert row is not None
    finally:
        con.close()
