#!/usr/bin/env python3
"""Validate minimal backup+restore operator reports for local instances."""

from __future__ import annotations

import argparse
from pathlib import Path


def _read_kv_report(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def _required(report: dict[str, str], keys: list[str], label: str) -> list[str]:
    return [f"{label}: missing key '{key}'" for key in keys if not report.get(key)]


def _validate_backup(report: dict[str, str], allow_warn: bool) -> list[str]:
    errors = _required(
        report,
        [
            "report_version",
            "mode",
            "tenant_id",
            "backup_file",
            "target_path",
            "checksum_sha256",
            "backup_size_bytes",
            "rto_seconds",
            "rpo_seconds",
        ],
        "backup_report",
    )

    verify_hook = report.get("backup_verify_hook", "")
    allowed_hooks = {"ok", "warn_skipped"} if allow_warn else {"ok"}
    if verify_hook not in allowed_hooks:
        errors.append(
            "backup_report: backup_verify_hook must be "
            f"{sorted(allowed_hooks)} but was '{verify_hook or '<missing>'}'"
        )

    if report.get("mode") not in {"nas", "degraded_local", "dry_run"}:
        errors.append(f"backup_report: unsupported mode '{report.get('mode', '<missing>')}'")

    return errors


def _validate_restore(report: dict[str, str], allow_warn: bool) -> list[str]:
    errors = _required(
        report,
        [
            "report_version",
            "mode",
            "tenant_id",
            "backup_file",
            "integrity_check",
            "verify_db",
            "verify_files",
            "restore_validation",
            "restore_verify_hook",
            "rto_seconds",
            "rpo_seconds",
        ],
        "restore_report",
    )

    if report.get("integrity_check") not in {"ok", "warn_missing_checksum", "warn_missing_metadata"}:
        errors.append(
            f"restore_report: unsupported integrity_check '{report.get('integrity_check', '<missing>')}'"
        )

    if report.get("verify_db") != "ok":
        errors.append(f"restore_report: verify_db must be 'ok' but was '{report.get('verify_db', '<missing>')}'")
    if report.get("verify_files") != "ok":
        errors.append(
            f"restore_report: verify_files must be 'ok' but was '{report.get('verify_files', '<missing>')}'"
        )

    allowed_validation = {"ok", "warn_missing_baseline"} if allow_warn else {"ok"}
    if report.get("restore_validation") not in allowed_validation:
        errors.append(
            "restore_report: restore_validation must be "
            f"{sorted(allowed_validation)} but was '{report.get('restore_validation', '<missing>')}'"
        )

    allowed_hook = {"ok", "warn_missing_baseline", "warn_skipped"} if allow_warn else {"ok"}
    if report.get("restore_verify_hook") not in allowed_hook:
        errors.append(
            "restore_report: restore_verify_hook must be "
            f"{sorted(allowed_hook)} but was '{report.get('restore_verify_hook', '<missing>')}'"
        )

    if report.get("mode") not in {"nas", "degraded_local"}:
        errors.append(f"restore_report: unsupported mode '{report.get('mode', '<missing>')}'")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup-report", required=True, help="Path to backup operator report")
    parser.add_argument("--restore-report", required=True, help="Path to restore operator report")
    parser.add_argument(
        "--allow-warn",
        action="store_true",
        help="Allow warning statuses (for degraded/offline environments)",
    )
    args = parser.parse_args()

    backup_path = Path(args.backup_report)
    restore_path = Path(args.restore_report)

    errors: list[str] = []
    if not backup_path.is_file():
        errors.append(f"backup_report not found: {backup_path}")
    if not restore_path.is_file():
        errors.append(f"restore_report not found: {restore_path}")

    if errors:
        for err in errors:
            print(f"ERROR: {err}")
        return 1

    backup_report = _read_kv_report(backup_path)
    restore_report = _read_kv_report(restore_path)

    errors.extend(_validate_backup(backup_report, allow_warn=args.allow_warn))
    errors.extend(_validate_restore(restore_report, allow_warn=args.allow_warn))

    if errors:
        for err in errors:
            print(f"ERROR: {err}")
        return 1

    print("OK: backup/restore minimum evidence verified")
    print(f"  backup_report={backup_path}")
    print(f"  restore_report={restore_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
