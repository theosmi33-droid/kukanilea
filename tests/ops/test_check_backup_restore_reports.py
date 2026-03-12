from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _write(path: Path, body: str) -> None:
    path.write_text(body.strip() + "\n", encoding="utf-8")


def test_report_check_passes_for_minimum_ok(tmp_path: Path) -> None:
    backup = tmp_path / "backup.txt"
    restore = tmp_path / "restore.txt"

    _write(
        backup,
        """
        report_version=1
        mode=degraded_local
        tenant_id=DEMO_TENANT
        backup_file=demo.tar.zst
        target_path=instance/degraded_backups/DEMO_TENANT/demo.tar.zst
        checksum_sha256=abcd
        backup_size_bytes=123
        backup_verify_hook=ok
        rto_seconds=1
        rpo_seconds=2
        """,
    )
    _write(
        restore,
        """
        report_version=1
        mode=degraded_local
        tenant_id=DEMO_TENANT
        backup_file=demo.tar.zst
        integrity_check=ok
        verify_db=ok
        verify_files=ok
        restore_validation=ok
        restore_verify_hook=ok
        rto_seconds=1
        rpo_seconds=2
        """,
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/ops/check_backup_restore_reports.py",
            "--backup-report",
            str(backup),
            "--restore-report",
            str(restore),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "minimum evidence verified" in result.stdout


def test_report_check_fails_without_required_status(tmp_path: Path) -> None:
    backup = tmp_path / "backup.txt"
    restore = tmp_path / "restore.txt"

    _write(
        backup,
        """
        report_version=1
        mode=degraded_local
        tenant_id=DEMO_TENANT
        backup_file=demo.tar.zst
        target_path=instance/degraded_backups/DEMO_TENANT/demo.tar.zst
        checksum_sha256=abcd
        backup_size_bytes=123
        backup_verify_hook=ok
        rto_seconds=1
        rpo_seconds=2
        """,
    )
    _write(
        restore,
        """
        report_version=1
        mode=degraded_local
        tenant_id=DEMO_TENANT
        backup_file=demo.tar.zst
        integrity_check=ok
        verify_db=failed
        verify_files=ok
        restore_validation=ok
        restore_verify_hook=ok
        rto_seconds=1
        rpo_seconds=2
        """,
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/ops/check_backup_restore_reports.py",
            "--backup-report",
            str(backup),
            "--restore-report",
            str(restore),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "verify_db must be ['ok']" in result.stdout


def test_report_check_requires_allow_warn_for_integrity_warnings(tmp_path: Path) -> None:
    backup = tmp_path / "backup.txt"
    restore = tmp_path / "restore.txt"

    _write(
        backup,
        """
        report_version=1
        mode=degraded_local
        tenant_id=DEMO_TENANT
        backup_file=demo.tar.zst
        target_path=instance/degraded_backups/DEMO_TENANT/demo.tar.zst
        checksum_sha256=abcd
        backup_size_bytes=123
        backup_verify_hook=ok
        rto_seconds=1
        rpo_seconds=2
        """,
    )
    _write(
        restore,
        """
        report_version=1
        mode=degraded_local
        tenant_id=DEMO_TENANT
        backup_file=demo.tar.zst
        integrity_check=warn_missing_checksum
        verify_db=warn_missing_sqlite3
        verify_files=ok
        restore_validation=ok
        restore_verify_hook=ok
        rto_seconds=1
        rpo_seconds=2
        """,
    )

    strict = subprocess.run(
        [
            sys.executable,
            "scripts/ops/check_backup_restore_reports.py",
            "--backup-report",
            str(backup),
            "--restore-report",
            str(restore),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert strict.returncode == 1
    assert "integrity_check must be ['ok']" in strict.stdout
    assert "verify_db must be ['ok']" in strict.stdout

    warn_allowed = subprocess.run(
        [
            sys.executable,
            "scripts/ops/check_backup_restore_reports.py",
            "--backup-report",
            str(backup),
            "--restore-report",
            str(restore),
            "--allow-warn",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert warn_allowed.returncode == 0
    assert "minimum evidence verified" in warn_allowed.stdout
