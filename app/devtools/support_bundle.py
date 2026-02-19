from __future__ import annotations

import json
import platform
import re
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.devtools.sandbox import resolve_core_db_path

TEST_MARKERS = (
    "pilot+test@example.com",
    "+49 151 12345678",
    "OCR_Test_2026-02-16_KD-9999",
)
POSIX_ABS_RE = re.compile(r"(?<![A-Za-z0-9>])/[^\s\"']+")
WINDOWS_DRIVE_RE = re.compile(r"[A-Za-z]:\\(?:[^\\\r\n]+\\)*[^\\\r\n]*")
WINDOWS_UNC_RE = re.compile(r"\\\\[A-Za-z0-9_.-]+\\(?:[^\\\r\n]+\\)*[^\\\r\n]*")

DEFAULT_SCHEMA_TABLES = (
    "autonomy_ocr_jobs",
    "knowledge_source_policies",
    "source_watch_config",
    "source_files",
    "knowledge_chunks",
    "events",
)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _table_exists(con: sqlite3.Connection, table_name: str) -> bool:
    row = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (table_name,),
    ).fetchone()
    return bool(row)


def _table_columns(con: sqlite3.Connection, table_name: str) -> set[str]:
    rows = con.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {str(r[1]) for r in rows}


def _sanitize_text(raw: str) -> str:
    text = str(raw or "").replace("\x00", "").replace("\r", "").strip()
    for marker in TEST_MARKERS:
        text = text.replace(marker, "<redacted>")
    text = WINDOWS_UNC_RE.sub("<path>", text)
    text = WINDOWS_DRIVE_RE.sub("<path>", text)
    text = POSIX_ABS_RE.sub("<path>", text)
    lines = [line for line in text.splitlines() if line]
    if len(lines) > 20:
        lines = lines[-20:]
    out = "\n".join(lines)
    if len(out) > 2000:
        out = out[-2000:]
    return out


def _sanitize_obj(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _sanitize_obj(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_obj(v) for v in value]
    if isinstance(value, tuple):
        return [_sanitize_obj(v) for v in value]
    if isinstance(value, str):
        return _sanitize_text(value)
    return value


def _path_for_output(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(Path.cwd().resolve()))
    except Exception:
        return f"<path>/{path.name}"


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        delete=False,
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
    ) as fh:
        fh.write(json.dumps(payload, sort_keys=True, indent=2) + "\n")
        tmp_name = fh.name
    Path(tmp_name).replace(path)


def _table_info(con: sqlite3.Connection, table: str) -> dict[str, Any]:
    row = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (table,),
    ).fetchone()
    if row is None:
        return {
            "exists": False,
            "reason": "missing_table",
            "columns": [],
        }
    rows = con.execute(f"PRAGMA table_info({table})").fetchall()
    cols = [
        {
            "cid": int(r[0]),
            "name": str(r[1]),
            "type": str(r[2] or ""),
            "notnull": int(r[3] or 0),
            "default": str(r[4]) if r[4] is not None else None,
            "pk": int(r[5] or 0),
        }
        for r in rows
    ]
    return {
        "exists": True,
        "reason": None,
        "columns": cols,
    }


def _schema_snapshot(core_db_path: Path, tables: tuple[str, ...]) -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "core_db_accessible": False,
        "tables": {},
    }
    con = sqlite3.connect(str(core_db_path))
    try:
        snapshot["core_db_accessible"] = True
        for table in tables:
            snapshot["tables"][table] = _table_info(con, table)
    except Exception as exc:
        snapshot["core_db_accessible"] = False
        snapshot["error"] = _sanitize_text(type(exc).__name__)
    finally:
        con.close()
    return snapshot


def collect_pilot_metrics(con: sqlite3.Connection, tenant_id: str) -> dict[str, Any]:
    tenant = str(tenant_id or "").strip() or "default"
    metrics: dict[str, Any] = {
        "tenant_id": tenant,
        "logins_last_14d": 0,
        "documents_total": 0,
        "tasks_total": 0,
        "automation_executions": 0,
        "active_rules": 0,
        "last_activity": None,
    }

    if _table_exists(con, "events") and {
        "event_type",
        "payload_json",
        "ts",
    }.issubset(_table_columns(con, "events")):
        row = con.execute(
            """
            SELECT COUNT(1) AS n
            FROM events
            WHERE event_type='user_login'
              AND payload_json LIKE ?
              AND ts >= datetime('now', '-14 days')
            """,
            (f'%"tenant_id":"{tenant}"%',),
        ).fetchone()
        metrics["logins_last_14d"] = int(row["n"] if row and row["n"] else 0)

        row = con.execute(
            """
            SELECT MAX(ts) AS ts
            FROM events
            WHERE payload_json LIKE ?
            """,
            (f'%"tenant_id":"{tenant}"%',),
        ).fetchone()
        metrics["last_activity"] = str(row["ts"]) if row and row["ts"] else None

    if _table_exists(con, "source_files") and "tenant_id" in _table_columns(
        con, "source_files"
    ):
        row = con.execute(
            "SELECT COUNT(1) AS n FROM source_files WHERE tenant_id=?",
            (tenant,),
        ).fetchone()
        metrics["documents_total"] = int(row["n"] if row and row["n"] else 0)

    if _table_exists(con, "tasks") and "tenant" in _table_columns(con, "tasks"):
        row = con.execute(
            "SELECT COUNT(1) AS n FROM tasks WHERE LOWER(COALESCE(tenant,''))=LOWER(?)",
            (tenant,),
        ).fetchone()
        metrics["tasks_total"] = int(row["n"] if row and row["n"] else 0)

    if _table_exists(con, "automation_builder_execution_log") and {
        "tenant_id",
        "status",
    }.issubset(_table_columns(con, "automation_builder_execution_log")):
        row = con.execute(
            """
            SELECT COUNT(1) AS n
            FROM automation_builder_execution_log
            WHERE tenant_id=? AND status='ok'
            """,
            (tenant,),
        ).fetchone()
        metrics["automation_executions"] = int(row["n"] if row and row["n"] else 0)
    elif _table_exists(con, "automation_runs") and {"tenant_id", "status"}.issubset(
        _table_columns(con, "automation_runs")
    ):
        row = con.execute(
            """
            SELECT COUNT(1) AS n
            FROM automation_runs
            WHERE tenant_id=? AND status='done'
            """,
            (tenant,),
        ).fetchone()
        metrics["automation_executions"] = int(row["n"] if row and row["n"] else 0)

    if _table_exists(con, "automation_builder_rules") and {
        "tenant_id",
        "is_enabled",
    }.issubset(_table_columns(con, "automation_builder_rules")):
        row = con.execute(
            """
            SELECT COUNT(1) AS n
            FROM automation_builder_rules
            WHERE tenant_id=? AND is_enabled=1
            """,
            (tenant,),
        ).fetchone()
        metrics["active_rules"] = int(row["n"] if row and row["n"] else 0)
    elif _table_exists(con, "automation_rules") and {"tenant_id", "enabled"}.issubset(
        _table_columns(con, "automation_rules")
    ):
        row = con.execute(
            """
            SELECT COUNT(1) AS n
            FROM automation_rules
            WHERE tenant_id=? AND enabled=1
            """,
            (tenant,),
        ).fetchone()
        metrics["active_rules"] = int(row["n"] if row and row["n"] else 0)

    return metrics


def _env_summary() -> dict[str, Any]:
    app_version = None
    try:
        import importlib.metadata as importlib_metadata

        app_version = importlib_metadata.version("kukanilea")
    except Exception:
        app_version = None
    return {
        "created_at_utc": _utcnow_iso(),
        "platform": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "app_version": app_version,
    }


def write_support_bundle(
    tenant_id: str,
    out_dir: Path,
    *,
    doctor_result: dict,
    sandbox_e2e_result: dict | None,
    extra: dict | None = None,
    atomic: bool = True,
    zip_bundle: bool = True,
) -> dict:
    tenant = str(tenant_id or "").strip() or "default"
    target_dir = Path(out_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    stage_dir = (
        target_dir / f".stage-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    )
    stage_dir.mkdir(parents=True, exist_ok=True)

    core_db_path = resolve_core_db_path()
    sanitized_doctor = _sanitize_obj(dict(doctor_result or {}))
    sanitized_e2e = (
        _sanitize_obj(dict(sandbox_e2e_result or {})) if sandbox_e2e_result else None
    )
    env_summary = _sanitize_obj(_env_summary())
    schema_snapshot = _sanitize_obj(
        _schema_snapshot(core_db_path, DEFAULT_SCHEMA_TABLES)
    )
    extra_payload = _sanitize_obj(dict(extra or {}))
    pilot_metrics: dict[str, Any] = {}

    try:
        con = sqlite3.connect(str(core_db_path))
        con.row_factory = sqlite3.Row
        try:
            pilot_metrics = collect_pilot_metrics(con, tenant)
        finally:
            con.close()
    except Exception:
        pilot_metrics = {}

    file_payloads: dict[str, Any] = {
        "ocr_doctor.json": sanitized_doctor,
        "env_summary.json": env_summary,
        "schema_snapshot.json": schema_snapshot,
    }
    if pilot_metrics:
        file_payloads["pilot_metrics.json"] = _sanitize_obj(pilot_metrics)
    if sanitized_e2e is not None:
        file_payloads["ocr_sandbox_e2e.json"] = sanitized_e2e
    if extra_payload:
        file_payloads["extra.json"] = extra_payload

    written_files: list[str] = []
    try:
        for name, payload in file_payloads.items():
            staged = stage_dir / name
            final = target_dir / name
            _atomic_write_json(staged, payload)
            if atomic:
                staged.replace(final)
            else:
                _atomic_write_json(final, payload)
            written_files.append(name)

        zip_name = None
        if zip_bundle:
            zip_final = target_dir / "support_bundle.zip"
            with tempfile.NamedTemporaryFile(
                "wb",
                delete=False,
                dir=str(target_dir),
                prefix=".support_bundle.",
                suffix=".zip",
            ) as fh:
                zip_tmp = Path(fh.name)
            with zipfile.ZipFile(zip_tmp, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for name in sorted(written_files):
                    zf.write(target_dir / name, arcname=name)
            zip_tmp.replace(zip_final)
            zip_name = zip_final.name

        manifest = {
            "ok": True,
            "reason": None,
            "tenant_id": tenant,
            "created_at_utc": _utcnow_iso(),
            "bundle_dir": _path_for_output(target_dir),
            "files": sorted(written_files),
            "zip_path": _path_for_output(target_dir / zip_name) if zip_name else None,
            "paths_sanitized": True,
        }
        _atomic_write_json(target_dir / "support_bundle_manifest.json", manifest)
        return manifest
    except Exception as exc:
        return {
            "ok": False,
            "reason": _sanitize_text(type(exc).__name__),
            "bundle_dir": _path_for_output(target_dir),
            "files": sorted(written_files),
            "zip_path": None,
        }
    finally:
        try:
            stage_dir.rmdir()
        except Exception:
            pass
