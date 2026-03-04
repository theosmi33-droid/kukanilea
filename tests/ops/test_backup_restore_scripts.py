from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
from pathlib import Path

import pytest


pytestmark = pytest.mark.skipif(
    shutil.which("zstd") is None or shutil.which("sqlite3") is None,
    reason="requires zstd and sqlite3 binaries",
)


def _prepare_instance(root: Path) -> None:
    inst = root / "instance"
    inst.mkdir(parents=True, exist_ok=True)
    (inst / "tenant_id.txt").write_text("DEMO_TENANT", encoding="utf-8")
    con = sqlite3.connect(inst / "auth.sqlite3")
    con.execute("CREATE TABLE IF NOT EXISTS demo(id TEXT)")
    con.execute("INSERT INTO demo(id) VALUES('1')")
    con.commit()
    con.close()


def test_backup_degraded_mode_writes_local_copy(tmp_path: Path) -> None:
    _prepare_instance(tmp_path)
    env = os.environ.copy()
    env["TENANT_ID"] = "DEMO_TENANT"
    env["NAS_SHARE"] = "//127.0.0.1/does-not-exist"
    env["LOCAL_FALLBACK_DIR"] = str(tmp_path / "instance" / "degraded_backups")
    env["REPORT_FILE"] = str(tmp_path / "instance" / "report_backup.txt")
    subprocess.run(["bash", str(Path.cwd() / "scripts/ops/backup_to_nas.sh")], cwd=tmp_path, env=env, check=True)
    files = list((tmp_path / "instance" / "degraded_backups" / "DEMO_TENANT").glob("*.tar.zst*"))
    assert files


def test_restore_degraded_mode_reads_local_copy(tmp_path: Path) -> None:
    _prepare_instance(tmp_path)
    # make a backup archive first
    (tmp_path / "instance" / "degraded_backups" / "DEMO_TENANT").mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["bash", "-c", "tar -C instance -cf - . | zstd -19 -T0 -o instance/degraded_backups/DEMO_TENANT/manual.tar.zst"],
        cwd=tmp_path,
        check=True,
    )
    env = os.environ.copy()
    env["TENANT_ID"] = "DEMO_TENANT"
    env["LOCAL_FALLBACK_DIR"] = str(tmp_path / "instance" / "degraded_backups")
    env["REPORT_FILE"] = str(tmp_path / "instance" / "report_restore.txt")
    subprocess.run(["bash", str(Path.cwd() / "scripts/ops/restore_from_nas.sh")], cwd=tmp_path, env=env, check=True)
    assert (tmp_path / "instance" / "report_restore.txt").exists()


def test_backup_operator_report_contains_rto_rpo(tmp_path: Path) -> None:
    _prepare_instance(tmp_path)
    env = os.environ.copy()
    env["TENANT_ID"] = "DEMO_TENANT"
    env["LOCAL_FALLBACK_DIR"] = str(tmp_path / "instance" / "degraded_backups")
    report = tmp_path / "instance" / "report_backup.txt"
    env["REPORT_FILE"] = str(report)
    subprocess.run(["bash", str(Path.cwd() / "scripts/ops/backup_to_nas.sh")], cwd=tmp_path, env=env, check=True)
    text = report.read_text(encoding="utf-8")
    assert "rto_seconds=" in text
    assert "rpo_seconds=" in text


def test_restore_operator_report_contains_mode(tmp_path: Path) -> None:
    _prepare_instance(tmp_path)
    (tmp_path / "instance" / "degraded_backups" / "DEMO_TENANT").mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["bash", "-c", "tar -C instance -cf - . | zstd -19 -T0 -o instance/degraded_backups/DEMO_TENANT/manual.tar.zst"],
        cwd=tmp_path,
        check=True,
    )
    report = tmp_path / "instance" / "report_restore.txt"
    env = os.environ.copy()
    env["TENANT_ID"] = "DEMO_TENANT"
    env["LOCAL_FALLBACK_DIR"] = str(tmp_path / "instance" / "degraded_backups")
    env["REPORT_FILE"] = str(report)
    subprocess.run(["bash", str(Path.cwd() / "scripts/ops/restore_from_nas.sh")], cwd=tmp_path, env=env, check=True)
    assert "mode=" in report.read_text(encoding="utf-8")
