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
    report = (tmp_path / "instance" / "report_backup.txt").read_text(encoding="utf-8")
    assert "mode=degraded_local" in report
    assert "degraded_reason=" in report


def test_restore_degraded_mode_requires_integrity_evidence(tmp_path: Path) -> None:
    _prepare_instance(tmp_path)
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
    result = subprocess.run(
        ["bash", str(Path.cwd() / "scripts/ops/restore_from_nas.sh")],
        cwd=tmp_path,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 4
    assert "checksum file missing" in result.stdout


def test_restore_degraded_mode_allows_explicit_unverified_override(tmp_path: Path) -> None:
    _prepare_instance(tmp_path)
    (tmp_path / "instance" / "degraded_backups" / "DEMO_TENANT").mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["bash", "-c", "tar -C instance -cf - . | zstd -19 -T0 -o instance/degraded_backups/DEMO_TENANT/manual.tar.zst"],
        cwd=tmp_path,
        check=True,
    )
    env = os.environ.copy()
    env["TENANT_ID"] = "DEMO_TENANT"
    env["LOCAL_FALLBACK_DIR"] = str(tmp_path / "instance" / "degraded_backups")
    env["ALLOW_UNVERIFIED_RESTORE"] = "1"
    env["REPORT_FILE"] = str(tmp_path / "instance" / "report_restore.txt")
    subprocess.run(["bash", str(Path.cwd() / "scripts/ops/restore_from_nas.sh")], cwd=tmp_path, env=env, check=True)
    report = (tmp_path / "instance" / "report_restore.txt").read_text(encoding="utf-8")
    assert "integrity_policy=allow_unverified" in report
    assert "checksum_verified=false" in report


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
    backup_env = os.environ.copy()
    backup_env["TENANT_ID"] = "DEMO_TENANT"
    backup_env["NAS_SHARE"] = "//127.0.0.1/does-not-exist"
    backup_env["LOCAL_FALLBACK_DIR"] = str(tmp_path / "instance" / "degraded_backups")
    backup_env["REPORT_FILE"] = str(tmp_path / "instance" / "backup_report.txt")
    subprocess.run(["bash", str(Path.cwd() / "scripts/ops/backup_to_nas.sh")], cwd=tmp_path, env=backup_env, check=True)

    report = tmp_path / "instance" / "report_restore.txt"
    env = os.environ.copy()
    env["TENANT_ID"] = "DEMO_TENANT"
    env["LOCAL_FALLBACK_DIR"] = str(tmp_path / "instance" / "degraded_backups")
    env["REPORT_FILE"] = str(report)
    subprocess.run(["bash", str(Path.cwd() / "scripts/ops/restore_from_nas.sh")], cwd=tmp_path, env=env, check=True)
    text = report.read_text(encoding="utf-8")
    assert "mode=" in text
    assert "degraded_reason=backup_resolved_from_local_fallback" in text
    assert "integrity_policy=strict" in text
    assert "verify_db=ok" in text
    assert "verify_files=ok" in text


def test_backup_writes_verifiable_artifacts_and_restore_compares(tmp_path: Path) -> None:
    _prepare_instance(tmp_path)
    env = os.environ.copy()
    env["TENANT_ID"] = "DEMO_TENANT"
    env["NAS_SHARE"] = "//127.0.0.1/does-not-exist"
    env["LOCAL_FALLBACK_DIR"] = str(tmp_path / "instance" / "degraded_backups")
    env["REPORT_FILE"] = str(tmp_path / "instance" / "backup_report.txt")
    subprocess.run(["bash", str(Path.cwd() / "scripts/ops/backup_to_nas.sh")], cwd=tmp_path, env=env, check=True)

    backup_report = (tmp_path / "instance" / "backup_report.txt").read_text(encoding="utf-8")
    assert "checksum_sha256=" in backup_report
    assert "backup_size_bytes=" in backup_report
    assert "target_path=" in backup_report
    assert "compression_ratio=" in backup_report
    assert "tenant_id=DEMO_TENANT" in backup_report

    report_map = dict(line.split("=", 1) for line in backup_report.splitlines() if "=" in line)
    backup_file = report_map["backup_file"]
    degraded_dir = tmp_path / "instance" / "degraded_backups" / "DEMO_TENANT"
    assert (degraded_dir / f"{backup_file}.metadata.json").exists()
    assert (degraded_dir / f"{backup_file}.snapshot.json").exists()

    restore_env = os.environ.copy()
    restore_env["TENANT_ID"] = "DEMO_TENANT"
    restore_env["LOCAL_FALLBACK_DIR"] = str(tmp_path / "instance" / "degraded_backups")
    restore_env["REPORT_FILE"] = str(tmp_path / "instance" / "restore_report.txt")
    subprocess.run(["bash", str(Path.cwd() / "scripts/ops/restore_from_nas.sh")], cwd=tmp_path, env=restore_env, check=True)
    restore_report = (tmp_path / "instance" / "restore_report.txt").read_text(encoding="utf-8")
    assert "integrity_check=ok" in restore_report
    assert "restore_validation=ok" in restore_report


def test_restore_fails_when_snapshot_missing(tmp_path: Path) -> None:
    _prepare_instance(tmp_path)
    env = os.environ.copy()
    env["TENANT_ID"] = "DEMO_TENANT"
    env["NAS_SHARE"] = "//127.0.0.1/does-not-exist"
    env["LOCAL_FALLBACK_DIR"] = str(tmp_path / "instance" / "degraded_backups")
    env["REPORT_FILE"] = str(tmp_path / "instance" / "backup_report.txt")
    subprocess.run(["bash", str(Path.cwd() / "scripts/ops/backup_to_nas.sh")], cwd=tmp_path, env=env, check=True)

    backup_report = (tmp_path / "instance" / "backup_report.txt").read_text(encoding="utf-8")
    report_map = dict(line.split("=", 1) for line in backup_report.splitlines() if "=" in line)
    backup_file = report_map["backup_file"]
    snapshot_path = tmp_path / "instance" / "degraded_backups" / "DEMO_TENANT" / f"{backup_file}.snapshot.json"
    snapshot_path.unlink()

    restore_env = os.environ.copy()
    restore_env["TENANT_ID"] = "DEMO_TENANT"
    restore_env["LOCAL_FALLBACK_DIR"] = str(tmp_path / "instance" / "degraded_backups")
    restore_env["REPORT_FILE"] = str(tmp_path / "instance" / "restore_report.txt")
    result = subprocess.run(
        ["bash", str(Path.cwd() / "scripts/ops/restore_from_nas.sh")],
        cwd=tmp_path,
        env=restore_env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 4
    assert "snapshot file missing" in result.stdout


def test_restore_fails_on_corrupted_artifact_checksum_mismatch(tmp_path: Path) -> None:
    _prepare_instance(tmp_path)
    env = os.environ.copy()
    env["TENANT_ID"] = "DEMO_TENANT"
    env["NAS_SHARE"] = "//127.0.0.1/does-not-exist"
    env["LOCAL_FALLBACK_DIR"] = str(tmp_path / "instance" / "degraded_backups")
    env["REPORT_FILE"] = str(tmp_path / "instance" / "backup_report.txt")
    subprocess.run(["bash", str(Path.cwd() / "scripts/ops/backup_to_nas.sh")], cwd=tmp_path, env=env, check=True)

    backup_report = (tmp_path / "instance" / "backup_report.txt").read_text(encoding="utf-8")
    report_map = dict(line.split("=", 1) for line in backup_report.splitlines() if "=" in line)
    backup_file = report_map["backup_file"]
    artifact_path = tmp_path / "instance" / "degraded_backups" / "DEMO_TENANT" / backup_file
    with artifact_path.open("ab") as handle:
        handle.write(b"\ncorruption\n")

    restore_env = os.environ.copy()
    restore_env["TENANT_ID"] = "DEMO_TENANT"
    restore_env["LOCAL_FALLBACK_DIR"] = str(tmp_path / "instance" / "degraded_backups")
    restore_env["REPORT_FILE"] = str(tmp_path / "instance" / "restore_report.txt")
    result = subprocess.run(
        ["bash", str(Path.cwd() / "scripts/ops/restore_from_nas.sh")],
        cwd=tmp_path,
        env=restore_env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 4
    assert "checksum mismatch" in result.stdout


def test_backup_artifacts_are_tenant_scoped(tmp_path: Path) -> None:
    _prepare_instance(tmp_path)
    env = os.environ.copy()
    env["TENANT_ID"] = "TENANT_A"
    env["NAS_SHARE"] = "//127.0.0.1/does-not-exist"
    env["LOCAL_FALLBACK_DIR"] = str(tmp_path / "instance" / "degraded_backups")
    env["REPORT_FILE"] = str(tmp_path / "instance" / "backup_report.txt")
    subprocess.run(["bash", str(Path.cwd() / "scripts/ops/backup_to_nas.sh")], cwd=tmp_path, env=env, check=True)

    tenant_dir = tmp_path / "instance" / "degraded_backups" / "TENANT_A"
    backup_files = list(tenant_dir.glob("TENANT_A_*.tar.zst*"))
    checksum_files = list(tenant_dir.glob("TENANT_A_*.sha256"))
    assert backup_files
    assert checksum_files
