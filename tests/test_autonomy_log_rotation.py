from __future__ import annotations

import os
import time
from pathlib import Path

import kukanilea_core_v3_fixed as core
from app.autonomy.maintenance import rotate_logs


def _init_core(tmp_path: Path) -> None:
    core.DB_PATH = tmp_path / "core.db"
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()


def test_rotate_logs_compresses_and_deletes_old_files(
    tmp_path: Path, monkeypatch
) -> None:
    _init_core(tmp_path)
    log_dir = tmp_path / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("KUKANILEA_LOG_DIR", str(log_dir))

    old_log = log_dir / "old.log"
    old_log.write_text("old", encoding="utf-8")
    old_gz = log_dir / "old.log.gz"
    old_gz.write_bytes(b"oldgz")
    fresh_log = log_dir / "fresh.log"
    fresh_log.write_text("fresh", encoding="utf-8")

    old_ts = time.time() - (40 * 24 * 3600)
    os.utime(old_log, (old_ts, old_ts))
    os.utime(old_gz, (old_ts, old_ts))

    result = rotate_logs("TENANT_A", actor_user_id="dev")
    assert result["ok"] is True
    assert result["compressed_count"] >= 1
    assert result["deleted_count"] >= 1
    assert fresh_log.exists()
    assert any(fp.suffix == ".gz" for fp in log_dir.iterdir())
