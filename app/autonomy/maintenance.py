from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from flask import current_app, has_app_context

import kukanilea_core_v3_fixed as legacy_core
from app.config import Config
from app.event_id_map import entity_id_int
from app.eventlog.core import event_append

DEFAULT_KEEP_DAYS = 7


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now_utc().isoformat(timespec="seconds")


def _core_db_path() -> Path:
    if has_app_context():
        return Path(current_app.config["CORE_DB"])
    return Path(Config.CORE_DB)


def _backup_dir() -> Path:
    env_dir = os.environ.get("KUKANILEA_BACKUP_DIR", "").strip()
    if has_app_context():
        cfg_dir = str(current_app.config.get("KUKANILEA_BACKUP_DIR", "")).strip()
        if cfg_dir:
            return Path(cfg_dir)
    if env_dir:
        return Path(env_dir)
    return Path(Config.USER_DATA_ROOT) / "backups"


def _keep_days() -> int:
    raw = os.environ.get("KUKANILEA_BACKUP_KEEP_DAYS", "").strip()
    try:
        days = int(raw) if raw else DEFAULT_KEEP_DAYS
    except Exception:
        days = DEFAULT_KEEP_DAYS
    return max(1, min(days, 365))


def _rotate_backups(target_dir: Path, keep_days: int) -> list[str]:
    cutoff = _now_utc() - timedelta(days=keep_days)
    removed: list[str] = []
    for fp in sorted(target_dir.glob("*.sqlite3")):
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


def _event_backup(
    *,
    ok: bool,
    tenant_scope: str,
    backup_name: str,
    size_bytes: int,
    rotated_count: int,
    actor_user_id: str | None,
    error_code: str | None = None,
) -> None:
    if has_app_context() and bool(current_app.config.get("READ_ONLY", False)):
        return
    event_type = "maintenance_backup_ok" if ok else "maintenance_backup_failed"
    payload = {
        "schema_version": 1,
        "source": "autonomy/maintenance",
        "actor_user_id": actor_user_id,
        "tenant_id": tenant_scope,
        "data": {
            "tenant_scope": tenant_scope,
            "backup_name": backup_name,
            "size_bytes": int(size_bytes),
            "rotated_count": int(rotated_count),
            "error_code": error_code or "",
        },
    }

    def _tx(con: sqlite3.Connection) -> None:
        event_append(
            event_type=event_type,
            entity_type="maintenance",
            entity_id=entity_id_int(f"backup:{tenant_scope}"),
            payload=payload,
            con=con,
        )

    try:
        legacy_core._run_write_txn(_tx)  # type: ignore[attr-defined]
    except Exception:
        return


def run_backup_once(
    tenant_id: str | None = None,
    actor_user_id: str | None = None,
    *,
    rotate: bool = True,
) -> dict[str, Any]:
    db_path = _core_db_path()
    backup_dir = _backup_dir()
    backup_dir.mkdir(parents=True, exist_ok=True)

    scope = (tenant_id or "all").strip() or "all"
    stamp = _now_utc().strftime("%Y%m%d-%H%M%S")
    backup_name = f"{scope}-{stamp}.sqlite3"
    backup_path = backup_dir / backup_name

    src: sqlite3.Connection | None = None
    dst: sqlite3.Connection | None = None
    removed: list[str] = []
    try:
        src = sqlite3.connect(str(db_path), timeout=30)
        try:
            src.execute("PRAGMA wal_checkpoint(PASSIVE)")
        except Exception:
            pass

        dst = sqlite3.connect(str(backup_path), timeout=30)
        src.backup(dst)
        dst.commit()

        if rotate:
            removed = _rotate_backups(backup_dir, _keep_days())

        size_bytes = int(backup_path.stat().st_size) if backup_path.exists() else 0
        _event_backup(
            ok=True,
            tenant_scope=scope,
            backup_name=backup_name,
            size_bytes=size_bytes,
            rotated_count=len(removed),
            actor_user_id=actor_user_id,
        )
        return {
            "ok": True,
            "tenant_scope": scope,
            "backup_name": backup_name,
            "size_bytes": size_bytes,
            "rotated": removed,
            "backup_dir": str(backup_dir),
            "created_at": _now_iso(),
        }
    except Exception as exc:
        _event_backup(
            ok=False,
            tenant_scope=scope,
            backup_name=backup_name,
            size_bytes=0,
            rotated_count=0,
            actor_user_id=actor_user_id,
            error_code=type(exc).__name__,
        )
        raise
    finally:
        if dst is not None:
            dst.close()
        if src is not None:
            src.close()
