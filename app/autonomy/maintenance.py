from __future__ import annotations

import gzip
import json
import os
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from flask import current_app, has_app_context

import kukanilea_core_v3_fixed as legacy_core
from app.config import Config
from app.event_id_map import entity_id_int
from app.eventlog.core import event_append

DEFAULT_BACKUP_KEEP_DAYS = 7
DEFAULT_LOG_KEEP_DAYS = 30
MAX_ERROR_SUMMARY = 240


def _tenant(tenant_id: str | None) -> str:
    tenant = legacy_core._effective_tenant(tenant_id or "")  # type: ignore[attr-defined]
    if not tenant:
        tenant = legacy_core._effective_tenant(legacy_core.TENANT_DEFAULT)  # type: ignore[attr-defined]
    return tenant or "default"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now_utc().isoformat(timespec="seconds")


def _new_id() -> str:
    return uuid.uuid4().hex


def _is_read_only() -> bool:
    if has_app_context():
        return bool(current_app.config.get("READ_ONLY", False))
    return False


def _core_db_path() -> Path:
    if has_app_context():
        return Path(str(current_app.config["CORE_DB"]))
    return Path(Config.CORE_DB)


def _backup_root_dir() -> Path:
    env_dir = os.environ.get("KUKANILEA_BACKUP_DIR", "").strip()
    if has_app_context():
        cfg_dir = str(current_app.config.get("KUKANILEA_BACKUP_DIR", "")).strip()
        if cfg_dir:
            return Path(cfg_dir)
    if env_dir:
        return Path(env_dir)
    return Path(Config.USER_DATA_ROOT) / "backups"


def _log_dir() -> Path:
    env_dir = os.environ.get("KUKANILEA_LOG_DIR", "").strip()
    if has_app_context():
        cfg_dir = str(current_app.config.get("KUKANILEA_LOG_DIR", "")).strip()
        if cfg_dir:
            return Path(cfg_dir)
    if env_dir:
        return Path(env_dir)
    return Path(Config.USER_DATA_ROOT) / "logs"


def _run_write_txn(fn):
    return legacy_core._run_write_txn(fn)  # type: ignore[attr-defined]


def _read_rows(sql: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
    with legacy_core._DB_LOCK:  # type: ignore[attr-defined]
        con = legacy_core._db()  # type: ignore[attr-defined]
        try:
            rows = con.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            con.close()


def _read_row(sql: str, params: tuple[Any, ...]) -> dict[str, Any] | None:
    rows = _read_rows(sql, params)
    return rows[0] if rows else None


def _status_defaults() -> dict[str, Any]:
    return {
        "backup_keep_days": DEFAULT_BACKUP_KEEP_DAYS,
        "log_keep_days": DEFAULT_LOG_KEEP_DAYS,
    }


def _parse_config_json(raw: Any) -> dict[str, Any]:
    if not raw:
        return _status_defaults()
    try:
        data = json.loads(str(raw))
    except Exception:
        return _status_defaults()
    if not isinstance(data, dict):
        return _status_defaults()
    merged = _status_defaults()
    for key in ("backup_keep_days", "log_keep_days"):
        try:
            value = int(data.get(key, merged[key]))
        except Exception:
            value = int(merged[key])
        if key == "backup_keep_days":
            value = max(1, min(value, 365))
        else:
            value = max(1, min(value, 3650))
        merged[key] = value
    return merged


def _status_get(tenant_id: str, create_if_missing: bool = True) -> dict[str, Any]:
    tenant = _tenant(tenant_id)
    row = _read_row(
        """
        SELECT tenant_id, last_backup_at, last_backup_size_bytes, last_backup_verified,
               last_log_rotation_at, last_smoke_test_at, last_smoke_test_result,
               config_json, updated_at
        FROM autonomy_maintenance_status
        WHERE tenant_id=?
        LIMIT 1
        """,
        (tenant,),
    )
    if row:
        return row
    defaults = {
        "tenant_id": tenant,
        "last_backup_at": None,
        "last_backup_size_bytes": None,
        "last_backup_verified": None,
        "last_log_rotation_at": None,
        "last_smoke_test_at": None,
        "last_smoke_test_result": None,
        "config_json": json.dumps(_status_defaults(), separators=(",", ":")),
        "updated_at": _now_iso(),
    }
    if not create_if_missing or _is_read_only():
        return defaults

    def _tx(con: sqlite3.Connection) -> dict[str, Any]:
        con.execute(
            """
            INSERT OR IGNORE INTO autonomy_maintenance_status(
              tenant_id, last_backup_at, last_backup_size_bytes, last_backup_verified,
              last_log_rotation_at, last_smoke_test_at, last_smoke_test_result,
              config_json, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (
                tenant,
                None,
                None,
                None,
                None,
                None,
                None,
                defaults["config_json"],
                defaults["updated_at"],
            ),
        )
        row2 = con.execute(
            """
            SELECT tenant_id, last_backup_at, last_backup_size_bytes, last_backup_verified,
                   last_log_rotation_at, last_smoke_test_at, last_smoke_test_result,
                   config_json, updated_at
            FROM autonomy_maintenance_status
            WHERE tenant_id=?
            LIMIT 1
            """,
            (tenant,),
        ).fetchone()
        return dict(row2) if row2 else defaults

    return _run_write_txn(_tx)


def _status_update(tenant_id: str, **fields: Any) -> dict[str, Any]:
    if _is_read_only():
        raise PermissionError("read_only")
    current = _status_get(tenant_id, create_if_missing=True)
    merged = dict(current)
    merged.update(fields)
    merged["updated_at"] = _now_iso()
    tenant = _tenant(tenant_id)

    def _tx(con: sqlite3.Connection) -> dict[str, Any]:
        con.execute(
            """
            INSERT OR REPLACE INTO autonomy_maintenance_status(
              tenant_id, last_backup_at, last_backup_size_bytes, last_backup_verified,
              last_log_rotation_at, last_smoke_test_at, last_smoke_test_result,
              config_json, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (
                tenant,
                merged.get("last_backup_at"),
                merged.get("last_backup_size_bytes"),
                merged.get("last_backup_verified"),
                merged.get("last_log_rotation_at"),
                merged.get("last_smoke_test_at"),
                merged.get("last_smoke_test_result"),
                merged.get("config_json")
                or json.dumps(_status_defaults(), separators=(",", ":")),
                merged["updated_at"],
            ),
        )
        row = con.execute(
            """
            SELECT tenant_id, last_backup_at, last_backup_size_bytes, last_backup_verified,
                   last_log_rotation_at, last_smoke_test_at, last_smoke_test_result,
                   config_json, updated_at
            FROM autonomy_maintenance_status
            WHERE tenant_id=?
            LIMIT 1
            """,
            (tenant,),
        ).fetchone()
        return dict(row) if row else merged

    return _run_write_txn(_tx)


def _event_emit(
    *,
    event_type: str,
    tenant_id: str,
    actor_user_id: str | None,
    data: dict[str, Any],
) -> None:
    if _is_read_only():
        return

    def _tx(con: sqlite3.Connection) -> None:
        event_append(
            event_type=event_type,
            entity_type="maintenance",
            entity_id=entity_id_int(f"{event_type}:{tenant_id}"),
            payload={
                "schema_version": 1,
                "source": "autonomy/maintenance",
                "actor_user_id": actor_user_id,
                "tenant_id": tenant_id,
                "data": data,
            },
            con=con,
        )

    try:
        _run_write_txn(_tx)
    except Exception:
        return


def _keep_days_from_status(tenant_id: str) -> tuple[int, int]:
    status = _status_get(tenant_id, create_if_missing=not _is_read_only())
    cfg = _parse_config_json(status.get("config_json"))
    backup_keep_days = int(cfg["backup_keep_days"])
    log_keep_days = int(cfg["log_keep_days"])
    return backup_keep_days, log_keep_days


def verify_backup(backup_path: Path | str) -> bool:
    path = Path(str(backup_path))
    if not path.exists() or not path.is_file():
        return False
    con: sqlite3.Connection | None = None
    try:
        con = sqlite3.connect(str(path))
        row = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name LIMIT 1"
        ).fetchone()
        if row is None:
            return False
        has_events = con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='events' LIMIT 1"
        ).fetchone()
        if has_events:
            con.execute("SELECT COUNT(*) FROM events").fetchone()
        return True
    except Exception:
        return False
    finally:
        if con is not None:
            con.close()


def _rotate_backups(target_dir: Path, keep_days: int) -> list[str]:
    cutoff = _now_utc() - timedelta(days=max(1, keep_days))
    removed: list[str] = []
    for fp in sorted(target_dir.glob("*.sqlite")):
        try:
            mtime = datetime.fromtimestamp(fp.stat().st_mtime, tz=timezone.utc)
        except Exception:
            continue
        if mtime < cutoff:
            try:
                fp.unlink()
                removed.append(fp.name)
            except Exception:
                continue
    return removed


def run_backup(
    tenant_id: str | None = None,
    actor_user_id: str | None = None,
    *,
    rotate: bool = True,
) -> dict[str, Any]:
    tenant = _tenant(tenant_id)
    if _is_read_only():
        return {
            "ok": False,
            "skipped": "read_only",
            "tenant_id": tenant,
            "created_at": _now_iso(),
        }

    backup_keep_days, log_keep_days = _keep_days_from_status(tenant)
    db_path = _core_db_path()
    target_dir = _backup_root_dir() / tenant
    target_dir.mkdir(parents=True, exist_ok=True)

    stamp = _now_utc().strftime("%Y%m%d-%H%M%S")
    backup_name = f"backup-{stamp}.sqlite"
    backup_path = target_dir / backup_name

    src: sqlite3.Connection | None = None
    dst: sqlite3.Connection | None = None
    try:
        src = sqlite3.connect(str(db_path), timeout=30)
        try:
            src.execute("PRAGMA wal_checkpoint(PASSIVE)")
        except Exception:
            pass
        dst = sqlite3.connect(str(backup_path), timeout=30)
        src.backup(dst)
        dst.commit()

        removed = _rotate_backups(target_dir, backup_keep_days) if rotate else []
        verified = verify_backup(backup_path)
        size_bytes = int(backup_path.stat().st_size) if backup_path.exists() else 0

        _status_update(
            tenant,
            last_backup_at=_now_iso(),
            last_backup_size_bytes=size_bytes,
            last_backup_verified=1 if verified else 0,
            config_json=json.dumps(
                {
                    "backup_keep_days": backup_keep_days,
                    "log_keep_days": log_keep_days,
                },
                separators=(",", ":"),
            ),
        )
        _event_emit(
            event_type="maintenance_backup_ok",
            tenant_id=tenant,
            actor_user_id=actor_user_id,
            data={
                "backup_size_bytes": size_bytes,
                "backup_verified": 1 if verified else 0,
                "rotated_count": len(removed),
            },
        )
        return {
            "ok": True,
            "tenant_id": tenant,
            "backup_name": backup_name,
            "backup_size_bytes": size_bytes,
            "backup_verified": bool(verified),
            "rotated": removed,
            "created_at": _now_iso(),
        }
    except Exception as exc:
        _event_emit(
            event_type="maintenance_backup_failed",
            tenant_id=tenant,
            actor_user_id=actor_user_id,
            data={"reason_code": type(exc).__name__},
        )
        return {
            "ok": False,
            "tenant_id": tenant,
            "error_code": type(exc).__name__,
            "created_at": _now_iso(),
        }
    finally:
        if dst is not None:
            dst.close()
        if src is not None:
            src.close()


def run_backup_once(
    tenant_id: str | None = None,
    actor_user_id: str | None = None,
    *,
    rotate: bool = True,
) -> dict[str, Any]:
    return run_backup(tenant_id=tenant_id, actor_user_id=actor_user_id, rotate=rotate)


def rotate_logs(
    tenant_id: str | None = None,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    tenant = _tenant(tenant_id)
    if _is_read_only():
        return {"ok": False, "tenant_id": tenant, "skipped": "read_only"}

    backup_keep_days, log_keep_days = _keep_days_from_status(tenant)
    log_dir = _log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    cutoff = _now_utc() - timedelta(days=log_keep_days)

    compressed = 0
    deleted = 0
    errors = 0
    for gz in sorted(log_dir.glob("*.gz")):
        try:
            mtime = datetime.fromtimestamp(gz.stat().st_mtime, tz=timezone.utc)
        except Exception:
            errors += 1
            continue
        if mtime >= cutoff:
            continue
        try:
            gz.unlink()
            deleted += 1
        except Exception:
            errors += 1

    for fp in sorted(log_dir.glob("*.log")):
        try:
            mtime = datetime.fromtimestamp(fp.stat().st_mtime, tz=timezone.utc)
        except Exception:
            errors += 1
            continue
        if mtime >= cutoff:
            continue
        gz_path = fp.with_suffix(fp.suffix + ".gz")
        try:
            with fp.open("rb") as src, gzip.open(gz_path, "wb", compresslevel=9) as dst:
                dst.write(src.read())
            fp.unlink()
            compressed += 1
        except Exception:
            errors += 1
            continue

    _status_update(
        tenant,
        last_log_rotation_at=_now_iso(),
        config_json=json.dumps(
            {
                "backup_keep_days": backup_keep_days,
                "log_keep_days": log_keep_days,
            },
            separators=(",", ":"),
        ),
    )
    _event_emit(
        event_type="maintenance_logs_rotated",
        tenant_id=tenant,
        actor_user_id=actor_user_id,
        data={
            "compressed_count": compressed,
            "deleted_count": deleted,
            "error_count": errors,
            "log_keep_days": log_keep_days,
        },
    )
    return {
        "ok": True,
        "tenant_id": tenant,
        "compressed_count": compressed,
        "deleted_count": deleted,
        "error_count": errors,
        "log_keep_days": log_keep_days,
        "created_at": _now_iso(),
    }


def record_scan_run(tenant_id: str, stats_dict: dict[str, Any]) -> dict[str, Any]:
    tenant = _tenant(tenant_id)
    if _is_read_only():
        return {"ok": False, "tenant_id": tenant, "skipped": "read_only"}

    started_at = str(stats_dict.get("started_at") or _now_iso())
    finished_at = str(stats_dict.get("finished_at") or _now_iso())
    status = str(stats_dict.get("status") or "ok").strip().lower()
    if status not in {"running", "ok", "error", "aborted"}:
        status = "error"

    files_scanned = int(stats_dict.get("files_scanned") or 0)
    files_ingested = int(stats_dict.get("files_ingested") or 0)
    files_skipped_dedup = int(stats_dict.get("files_skipped_dedup") or 0)
    files_skipped_exclude = int(stats_dict.get("files_skipped_exclude") or 0)
    files_failed = int(stats_dict.get("files_failed") or 0)
    error_summary = str(stats_dict.get("error_summary") or "").strip()[
        :MAX_ERROR_SUMMARY
    ]

    run_id = _new_id()

    def _tx(con: sqlite3.Connection) -> dict[str, Any]:
        con.execute(
            """
            INSERT INTO autonomy_scan_history(
              id, tenant_id, started_at, finished_at, status,
              files_scanned, files_ingested, files_skipped_dedup,
              files_skipped_exclude, files_failed, error_summary, created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                run_id,
                tenant,
                started_at,
                finished_at,
                status,
                files_scanned,
                files_ingested,
                files_skipped_dedup,
                files_skipped_exclude,
                files_failed,
                error_summary,
                _now_iso(),
            ),
        )
        return {
            "id": run_id,
            "tenant_id": tenant,
            "started_at": started_at,
            "finished_at": finished_at,
            "status": status,
            "files_scanned": files_scanned,
            "files_ingested": files_ingested,
            "files_skipped_dedup": files_skipped_dedup,
            "files_skipped_exclude": files_skipped_exclude,
            "files_failed": files_failed,
            "error_summary": error_summary,
        }

    result = _run_write_txn(_tx)
    return {"ok": True, "scan_run": result}


def scan_history_list(tenant_id: str, limit: int = 20) -> list[dict[str, Any]]:
    tenant = _tenant(tenant_id)
    lim = max(1, min(int(limit), 200))
    rows = _read_rows(
        """
        SELECT id, tenant_id, started_at, finished_at, status,
               files_scanned, files_ingested, files_skipped_dedup,
               files_skipped_exclude, files_failed, error_summary, created_at
        FROM autonomy_scan_history
        WHERE tenant_id=?
        ORDER BY started_at DESC, id DESC
        LIMIT ?
        """,
        (tenant, lim),
    )
    return rows


def run_smoke_test(
    tenant_id: str,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    tenant = _tenant(tenant_id)
    if _is_read_only():
        return {"ok": False, "tenant_id": tenant, "skipped": "read_only"}

    checks: list[dict[str, Any]] = []
    severity = "ok"

    try:
        _read_row("SELECT 1 AS ok", ())
        checks.append({"name": "db_access", "ok": True})
    except Exception:
        checks.append({"name": "db_access", "ok": False})
        severity = "error"

    cfg_exists = _read_row(
        "SELECT tenant_id FROM source_watch_config WHERE tenant_id=? LIMIT 1",
        (tenant,),
    )
    checks.append({"name": "source_watch_config", "ok": bool(cfg_exists)})

    latest_scan = _read_row(
        """
        SELECT started_at, status
        FROM autonomy_scan_history
        WHERE tenant_id=?
        ORDER BY started_at DESC, id DESC
        LIMIT 1
        """,
        (tenant,),
    )
    if latest_scan and latest_scan.get("started_at"):
        try:
            dt = datetime.fromisoformat(str(latest_scan["started_at"]))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            recent = (_now_utc() - dt) <= timedelta(days=7)
        except Exception:
            recent = False
    else:
        recent = False
    checks.append({"name": "scan_recency", "ok": recent})
    if not recent and severity == "ok":
        severity = "warn"

    recent_errors = _read_row(
        """
        SELECT COUNT(*) AS c
        FROM autonomy_scan_history
        WHERE tenant_id=? AND status='error' AND started_at>=?
        """,
        (tenant, (_now_utc() - timedelta(days=1)).isoformat(timespec="seconds")),
    )
    error_count = int((recent_errors or {}).get("c") or 0)
    checks.append(
        {"name": "recent_scan_errors", "ok": error_count == 0, "count": error_count}
    )
    if error_count > 0 and severity == "ok":
        severity = "warn"

    _status_update(
        tenant,
        last_smoke_test_at=_now_iso(),
        last_smoke_test_result=severity,
    )
    _event_emit(
        event_type="maintenance_smoke_test",
        tenant_id=tenant,
        actor_user_id=actor_user_id,
        data={"result": severity, "checks_total": len(checks)},
    )
    return {
        "ok": severity == "ok",
        "tenant_id": tenant,
        "result": severity,
        "checks": checks,
        "created_at": _now_iso(),
    }


def get_health_overview(tenant_id: str, history_limit: int = 20) -> dict[str, Any]:
    tenant = _tenant(tenant_id)
    status = _status_get(tenant, create_if_missing=not _is_read_only())
    cfg = _parse_config_json(status.get("config_json"))
    history = scan_history_list(tenant, limit=history_limit)
    latest_scan = history[0] if history else None

    day_ago = (_now_utc() - timedelta(days=1)).isoformat(timespec="seconds")
    ingest_24h = _read_rows(
        """
        SELECT action, COUNT(*) AS c
        FROM source_ingest_log
        WHERE tenant_id=? AND created_at>=?
        GROUP BY action
        ORDER BY action ASC
        """,
        (tenant, day_ago),
    )
    ingest_counts = {str(r["action"]): int(r["c"]) for r in ingest_24h}
    return {
        "tenant_id": tenant,
        "status": status,
        "config": cfg,
        "latest_scan": latest_scan,
        "scan_history": history,
        "ingest_24h": ingest_counts,
        "generated_at": _now_iso(),
    }
