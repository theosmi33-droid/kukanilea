from __future__ import annotations

import json
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
    con.execute("CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY, tenant_id TEXT, name TEXT)")
    con.execute("CREATE TABLE IF NOT EXISTS contacts(id TEXT PRIMARY KEY, tenant_id TEXT, email TEXT)")
    con.execute("INSERT OR REPLACE INTO projects(id, tenant_id, name) VALUES('p1','DEMO_TENANT','Project')")
    con.execute("INSERT OR REPLACE INTO contacts(id, tenant_id, email) VALUES('c1','DEMO_TENANT','demo@example.com')")
    con.commit()
    con.close()


def _write_minimal_tool_path(root: Path, include_smbclient: bool) -> str:
    bindir = root / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    required = [
        "awk",
        "basename",
        "cat",
        "cp",
        "cut",
        "date",
        "dirname",
        "head",
        "ls",
        "mkdir",
        "python3",
        "rm",
        "sed",
        "sha256sum",
        "shasum",
        "sleep",
        "sqlite3",
        "stat",
        "tail",
        "tar",
        "tr",
        "zstd",
    ]
    if include_smbclient:
        required.append("smbclient")
    for tool in required:
        source = shutil.which(tool)
        if source:
            (bindir / tool).symlink_to(source)
    return str(bindir)


def _run_backup(tmp_path: Path, *, hide_smbclient: bool = False) -> tuple[subprocess.CompletedProcess[str], dict[str, str]]:
    env = os.environ.copy()
    env["TENANT_ID"] = "DEMO_TENANT"
    env["NAS_SHARE"] = "//127.0.0.1/does-not-exist"
    env["LOCAL_FALLBACK_DIR"] = str(tmp_path / "instance" / "degraded_backups")
    env["REPORT_FILE"] = str(tmp_path / "instance" / "report_backup.txt")
    if hide_smbclient:
        env["PATH"] = _write_minimal_tool_path(tmp_path / "path_without_smb", include_smbclient=False)
    run = subprocess.run(
        ["bash", str(Path.cwd() / "scripts/ops/backup_to_nas.sh")],
        cwd=tmp_path,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return run, env


def _run_restore(
    tmp_path: Path,
    backup_file: str,
    *,
    baseline_path: Path | None = None,
    hide_smbclient: bool = False,
) -> tuple[subprocess.CompletedProcess[str], dict[str, str]]:
    env = os.environ.copy()
    env["TENANT_ID"] = "DEMO_TENANT"
    env["BACKUP_FILE"] = backup_file
    env["LOCAL_FALLBACK_DIR"] = str(tmp_path / "instance" / "degraded_backups")
    env["REPORT_FILE"] = str(tmp_path / "instance" / "report_restore.txt")
    if baseline_path is not None:
        env["BASELINE_PATH"] = str(baseline_path)
    if hide_smbclient:
        env["PATH"] = _write_minimal_tool_path(tmp_path / "path_without_smb_restore", include_smbclient=False)
    run = subprocess.run(
        ["bash", str(Path.cwd() / "scripts/ops/restore_from_nas.sh")],
        cwd=tmp_path,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return run, env


def _first_backup_file(tmp_path: Path) -> Path:
    files = sorted((tmp_path / "instance" / "degraded_backups" / "DEMO_TENANT").glob("*.tar.zst*"))
    assert files
    return files[-1]


def _parse_report(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            data[key] = value
    return data


def test_backup_degraded_mode_without_smbclient_writes_local_copy(tmp_path: Path) -> None:
    _prepare_instance(tmp_path)
    _run_backup(tmp_path, hide_smbclient=True)
    files = list((tmp_path / "instance" / "degraded_backups" / "DEMO_TENANT").glob("*.tar.zst*"))
    assert files


def test_backup_writes_metadata_and_snapshot_artifacts(tmp_path: Path) -> None:
    _prepare_instance(tmp_path)
    _run_backup(tmp_path, hide_smbclient=True)
    backup = _first_backup_file(tmp_path)
    metadata = backup.with_name(f"{backup.name}.metadata.json")
    snapshot = backup.with_name(f"{backup.name}.snapshot.json")
    assert metadata.exists()
    assert snapshot.exists()
    metadata_payload = json.loads(metadata.read_text(encoding="utf-8"))
    snapshot_payload = json.loads(snapshot.read_text(encoding="utf-8"))
    assert metadata_payload["backup_file"] == backup.name
    assert "checksum_sha256" in metadata_payload
    assert isinstance(snapshot_payload, dict)


def test_backup_operator_report_contains_artifact_entries(tmp_path: Path) -> None:
    _prepare_instance(tmp_path)
    _, env = _run_backup(tmp_path, hide_smbclient=True)
    report = _parse_report(Path(env["REPORT_FILE"]))
    assert report["mode"] == "degraded_local"
    assert report["metadata_file"].endswith(".metadata.json")
    assert report["snapshot_file"].endswith(".snapshot.json")


def test_restore_degraded_mode_reads_local_copy(tmp_path: Path) -> None:
    _prepare_instance(tmp_path)
    _run_backup(tmp_path, hide_smbclient=True)
    backup = _first_backup_file(tmp_path)
    _run_restore(tmp_path, backup.name, hide_smbclient=True)
    assert (tmp_path / "instance" / "report_restore.txt").exists()


def test_backup_writes_verifiable_artifacts_and_restore_compares(tmp_path: Path) -> None:
    _prepare_instance(tmp_path)
    _run_backup(tmp_path, hide_smbclient=True)
    backup = _first_backup_file(tmp_path)

    con = sqlite3.connect(tmp_path / "instance" / "auth.sqlite3")
    con.execute("DELETE FROM contacts")
    con.commit()
    con.close()

    _run_restore(tmp_path, backup.name, hide_smbclient=True)
    report = _parse_report(tmp_path / "instance" / "report_restore.txt")
    assert report["snapshot_status"] == "loaded"
    assert report["restore_validation"] == "ok"


def test_restore_missing_snapshot_uses_baseline_fallback(tmp_path: Path) -> None:
    _prepare_instance(tmp_path)
    _run_backup(tmp_path, hide_smbclient=True)
    backup = _first_backup_file(tmp_path)
    snapshot = backup.with_name(f"{backup.name}.snapshot.json")
    snapshot.unlink()

    baseline = tmp_path / "instance" / "restore_baseline.json"
    subprocess.run(
        [
            "python3",
            str(Path.cwd() / "scripts/ops/restore_validation.py"),
            "--phase",
            "before",
            "--tenant",
            "DEMO_TENANT",
            "--db",
            str(tmp_path / "instance" / "auth.sqlite3"),
            "--baseline",
            str(baseline),
        ],
        cwd=tmp_path,
        check=True,
    )

    _run_restore(tmp_path, backup.name, baseline_path=baseline, hide_smbclient=True)
    report = _parse_report(tmp_path / "instance" / "report_restore.txt")
    assert report["snapshot_status"] == "missing"
    assert report["restore_validation"] == "ok"


def test_restore_corrupted_snapshot_handled_cleanly(tmp_path: Path) -> None:
    _prepare_instance(tmp_path)
    _run_backup(tmp_path, hide_smbclient=True)
    backup = _first_backup_file(tmp_path)
    snapshot = backup.with_name(f"{backup.name}.snapshot.json")
    snapshot.write_text("{not-json", encoding="utf-8")

    baseline = tmp_path / "instance" / "restore_baseline.json"
    subprocess.run(
        [
            "python3",
            str(Path.cwd() / "scripts/ops/restore_validation.py"),
            "--phase",
            "before",
            "--tenant",
            "DEMO_TENANT",
            "--db",
            str(tmp_path / "instance" / "auth.sqlite3"),
            "--baseline",
            str(baseline),
        ],
        cwd=tmp_path,
        check=True,
    )

    _run_restore(tmp_path, backup.name, baseline_path=baseline, hide_smbclient=True)
    report = _parse_report(tmp_path / "instance" / "report_restore.txt")
    assert report["snapshot_status"] == "corrupted"
    assert report["restore_validation"] == "warn_corrupted_snapshot"


def test_restore_operator_report_contains_mode(tmp_path: Path) -> None:
    _prepare_instance(tmp_path)
    _run_backup(tmp_path, hide_smbclient=True)
    backup = _first_backup_file(tmp_path)
    _run_restore(tmp_path, backup.name, hide_smbclient=True)
    assert "mode=" in (tmp_path / "instance" / "report_restore.txt").read_text(encoding="utf-8")
