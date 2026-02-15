from __future__ import annotations

import hashlib
import hmac
import os
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import current_app, has_app_context

import kukanilea_core_v3_fixed as legacy_core
from app.event_id_map import entity_id_int
from app.eventlog.core import event_append
from app.knowledge import (
    knowledge_document_ingest,
    knowledge_email_ingest_eml,
    knowledge_ics_ingest,
)

SOURCE_KINDS = {"document", "email", "calendar"}
DOCUMENT_EXTS = {".pdf", ".txt", ".md", ".png", ".jpg", ".jpeg", ".tiff", ".tif"}
EMAIL_EXTS = {".eml"}
CALENDAR_EXTS = {".ics"}

DEFAULT_MAX_BYTES = 262_144
DEFAULT_DOC_MAX_BYTES = 5 * 1024 * 1024
DEFAULT_MAX_FILES = 200
DEFAULT_BUDGET_MS = 1500

MAX_FILES_HARD = 2_000
MAX_BYTES_HARD = 20 * 1024 * 1024
MAX_DIR_LEN = 1024


class ConfigError(RuntimeError):
    """Raised when required scanner configuration is invalid."""


def _tenant(tenant_id: str) -> str:
    t = legacy_core._effective_tenant(tenant_id) or legacy_core._effective_tenant(  # type: ignore[attr-defined]
        legacy_core.TENANT_DEFAULT
    )
    return t or "default"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _new_id() -> str:
    return uuid.uuid4().hex


def _is_read_only() -> bool:
    if has_app_context():
        return bool(current_app.config.get("READ_ONLY", False))
    return False


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


def _clean_dir(value: str | None) -> str | None:
    v = str(value or "").replace("\x00", "").strip()
    if not v:
        return None
    if len(v) > MAX_DIR_LEN:
        raise ValueError("validation_error")
    return v


def _config_defaults(tenant_id: str) -> dict[str, Any]:
    return {
        "tenant_id": tenant_id,
        "documents_inbox_dir": None,
        "email_inbox_dir": None,
        "calendar_inbox_dir": None,
        "enabled": 1,
        "max_bytes_per_file": DEFAULT_MAX_BYTES,
        "max_files_per_scan": DEFAULT_MAX_FILES,
        "updated_at": _now_iso(),
    }


def source_watch_config_get(
    tenant_id: str, *, create_if_missing: bool = True
) -> dict[str, Any]:
    tenant = _tenant(tenant_id)
    row = _read_row(
        """
        SELECT tenant_id, documents_inbox_dir, email_inbox_dir, calendar_inbox_dir,
               enabled, max_bytes_per_file, max_files_per_scan, updated_at
        FROM source_watch_config
        WHERE tenant_id=?
        LIMIT 1
        """,
        (tenant,),
    )
    if row:
        return row
    defaults = _config_defaults(tenant)
    if not create_if_missing or _is_read_only():
        return defaults

    def _tx(con: sqlite3.Connection) -> dict[str, Any]:
        con.execute(
            """
            INSERT OR IGNORE INTO source_watch_config(
              tenant_id, documents_inbox_dir, email_inbox_dir, calendar_inbox_dir,
              enabled, max_bytes_per_file, max_files_per_scan, updated_at
            ) VALUES (?,?,?,?,?,?,?,?)
            """,
            (
                tenant,
                defaults["documents_inbox_dir"],
                defaults["email_inbox_dir"],
                defaults["calendar_inbox_dir"],
                int(defaults["enabled"]),
                int(defaults["max_bytes_per_file"]),
                int(defaults["max_files_per_scan"]),
                defaults["updated_at"],
            ),
        )
        row2 = con.execute(
            """
            SELECT tenant_id, documents_inbox_dir, email_inbox_dir, calendar_inbox_dir,
                   enabled, max_bytes_per_file, max_files_per_scan, updated_at
            FROM source_watch_config
            WHERE tenant_id=?
            LIMIT 1
            """,
            (tenant,),
        ).fetchone()
        return dict(row2) if row2 else defaults

    return _run_write_txn(_tx)


def source_watch_config_update(
    tenant_id: str,
    *,
    documents_inbox_dir: str | None = None,
    email_inbox_dir: str | None = None,
    calendar_inbox_dir: str | None = None,
    enabled: bool | None = None,
    max_bytes_per_file: int | None = None,
    max_files_per_scan: int | None = None,
) -> dict[str, Any]:
    if _is_read_only():
        raise PermissionError("read_only")

    tenant = _tenant(tenant_id)
    current = source_watch_config_get(tenant, create_if_missing=True)
    next_row = dict(current)

    if documents_inbox_dir is not None:
        next_row["documents_inbox_dir"] = _clean_dir(documents_inbox_dir)
    if email_inbox_dir is not None:
        next_row["email_inbox_dir"] = _clean_dir(email_inbox_dir)
    if calendar_inbox_dir is not None:
        next_row["calendar_inbox_dir"] = _clean_dir(calendar_inbox_dir)
    if enabled is not None:
        next_row["enabled"] = 1 if bool(enabled) else 0
    if max_bytes_per_file is not None:
        val = max(1024, min(int(max_bytes_per_file), MAX_BYTES_HARD))
        next_row["max_bytes_per_file"] = val
    if max_files_per_scan is not None:
        val = max(1, min(int(max_files_per_scan), MAX_FILES_HARD))
        next_row["max_files_per_scan"] = val
    next_row["updated_at"] = _now_iso()

    def _tx(con: sqlite3.Connection) -> dict[str, Any]:
        con.execute(
            """
            INSERT OR REPLACE INTO source_watch_config(
              tenant_id, documents_inbox_dir, email_inbox_dir, calendar_inbox_dir,
              enabled, max_bytes_per_file, max_files_per_scan, updated_at
            ) VALUES (?,?,?,?,?,?,?,?)
            """,
            (
                tenant,
                next_row.get("documents_inbox_dir"),
                next_row.get("email_inbox_dir"),
                next_row.get("calendar_inbox_dir"),
                int(next_row.get("enabled", 1)),
                int(next_row.get("max_bytes_per_file", DEFAULT_MAX_BYTES)),
                int(next_row.get("max_files_per_scan", DEFAULT_MAX_FILES)),
                str(next_row.get("updated_at") or _now_iso()),
            ),
        )
        row = con.execute(
            """
            SELECT tenant_id, documents_inbox_dir, email_inbox_dir, calendar_inbox_dir,
                   enabled, max_bytes_per_file, max_files_per_scan, updated_at
            FROM source_watch_config
            WHERE tenant_id=?
            LIMIT 1
            """,
            (tenant,),
        ).fetchone()
        return dict(row) if row else next_row

    return _run_write_txn(_tx)


def _get_path_hmac_key() -> bytes:
    if has_app_context():
        cfg_key = current_app.config.get("ANONYMIZATION_KEY")
        if cfg_key:
            if isinstance(cfg_key, bytes):
                return cfg_key
            return str(cfg_key).encode("utf-8")

    env_key = os.environ.get("KUKANILEA_ANONYMIZATION_KEY")
    if env_key:
        return env_key.encode("utf-8")

    if has_app_context():
        secret = current_app.config.get("SECRET_KEY")
        if secret:
            if isinstance(secret, bytes):
                return secret
            return str(secret).encode("utf-8")

    fallback = os.environ.get("KUKANILEA_SECRET")
    if fallback:
        return fallback.encode("utf-8")

    raise ConfigError("missing_anonymization_key")


def _normalize_path(path: str) -> str:
    try:
        p = Path(path).resolve()
    except Exception:
        p = Path(path)
    value = p.as_posix().replace("\x00", "").strip()
    return value


def hmac_path_hash(path: str) -> str:
    key = _get_path_hmac_key()
    msg = _normalize_path(path).encode("utf-8")
    return hmac.new(key, msg, hashlib.sha256).hexdigest()


def _looks_maildir(root: Path) -> bool:
    return (root / "cur").is_dir() and (root / "new").is_dir()


def _iter_files(root: Path) -> list[Path]:
    out: list[Path] = []

    def _walk(path: Path) -> None:
        try:
            entries = sorted(path.iterdir(), key=lambda p: p.name.lower())
        except Exception:
            return
        for entry in entries:
            if entry.is_symlink():
                continue
            if entry.is_dir():
                _walk(entry)
                continue
            if entry.is_file():
                out.append(entry)

    if root.exists() and root.is_dir():
        _walk(root)
    return out


def _maildir_files(root: Path) -> list[Path]:
    out: list[Path] = []
    for sub in ("new", "cur"):
        out.extend(_iter_files(root / sub))
    return out


def _fingerprint(path: Path, st: os.stat_result) -> str:
    raw = f"{path.name}|{int(st.st_size)}|{int(st.st_mtime_ns)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _doc_limit(cfg: dict[str, Any]) -> int:
    env_val = os.environ.get("KUKANILEA_AUTONOMY_DOC_MAX_BYTES", "")
    try:
        configured = int(env_val) if env_val else DEFAULT_DOC_MAX_BYTES
    except Exception:
        configured = DEFAULT_DOC_MAX_BYTES
    table_val = int(cfg.get("max_bytes_per_file") or DEFAULT_MAX_BYTES)
    return max(1024, min(max(configured, table_val), MAX_BYTES_HARD))


def _kind_limit(kind: str, cfg: dict[str, Any]) -> int:
    if kind == "document":
        return _doc_limit(cfg)
    return max(
        1024,
        min(int(cfg.get("max_bytes_per_file") or DEFAULT_MAX_BYTES), MAX_BYTES_HARD),
    )


def _touch_source_file(
    tenant_id: str,
    source_kind: str,
    path_hash: str,
    fingerprint: str,
) -> dict[str, Any]:
    now = _now_iso()

    def _tx(con: sqlite3.Connection) -> dict[str, Any]:
        row = con.execute(
            """
            SELECT id, fingerprint, status, first_seen_at
            FROM source_files
            WHERE tenant_id=? AND source_kind=? AND path_hash=?
            LIMIT 1
            """,
            (tenant_id, source_kind, path_hash),
        ).fetchone()
        if not row:
            source_file_id = _new_id()
            con.execute(
                """
                INSERT INTO source_files(
                  id, tenant_id, source_kind, path_hash, fingerprint, status,
                  last_seen_at, first_seen_at, last_ingested_at, last_error_code
                ) VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    source_file_id,
                    tenant_id,
                    source_kind,
                    path_hash,
                    fingerprint,
                    "new",
                    now,
                    now,
                    None,
                    None,
                ),
            )
            return {
                "id": source_file_id,
                "changed": True,
                "is_new": True,
                "status": "new",
                "fingerprint": fingerprint,
            }

        source_file_id = str(row["id"])
        old_fp = str(row["fingerprint"] or "")
        old_status = str(row["status"] or "new")
        changed = old_fp != fingerprint or old_status != "ingested"
        next_status = "new" if changed else old_status
        con.execute(
            """
            UPDATE source_files
            SET fingerprint=?, status=?, last_seen_at=?
            WHERE tenant_id=? AND source_kind=? AND path_hash=?
            """,
            (fingerprint, next_status, now, tenant_id, source_kind, path_hash),
        )
        return {
            "id": source_file_id,
            "changed": changed,
            "is_new": False,
            "status": next_status,
            "fingerprint": fingerprint,
        }

    return _run_write_txn(_tx)


def _record_outcome(
    *,
    tenant_id: str,
    source_file_id: str,
    source_kind: str,
    path_hash: str,
    action: str,
    detail_code: str,
    actor_user_id: str | None,
) -> None:
    now = _now_iso()

    def _tx(con: sqlite3.Connection) -> None:
        if action == "ingest_ok":
            status = "ingested"
            last_ingested_at = now
            last_error = None
            event_type = "source_file_ingested"
        elif action == "ingest_failed":
            status = "failed"
            last_ingested_at = None
            last_error = detail_code
            event_type = "source_file_ingest_failed"
        else:
            status = "skipped"
            last_ingested_at = None
            last_error = detail_code
            event_type = "source_file_ingest_skipped"

        con.execute(
            """
            UPDATE source_files
            SET status=?,
                last_ingested_at=COALESCE(?, last_ingested_at),
                last_error_code=?,
                last_seen_at=?
            WHERE tenant_id=? AND id=?
            """,
            (status, last_ingested_at, last_error, now, tenant_id, source_file_id),
        )
        con.execute(
            """
            INSERT INTO source_ingest_log(
              id, tenant_id, source_kind, path_hash, action, detail_code, created_at
            ) VALUES (?,?,?,?,?,?,?)
            """,
            (
                _new_id(),
                tenant_id,
                source_kind,
                path_hash,
                action,
                detail_code,
                now,
            ),
        )
        event_append(
            event_type=event_type,
            entity_type="source_file",
            entity_id=entity_id_int(source_file_id),
            payload={
                "schema_version": 1,
                "source": "autonomy/source_scan",
                "actor_user_id": actor_user_id,
                "tenant_id": tenant_id,
                "data": {
                    "source_kind": source_kind,
                    "path_hash": path_hash,
                    "action": action,
                    "detail_code": detail_code,
                },
            },
            con=con,
        )

    _run_write_txn(_tx)


def _extract_document_text(path: Path, data: bytes) -> str:
    text_exts = {".txt", ".md", ".json", ".csv", ".log", ".xml"}
    ext = path.suffix.lower()
    text = ""
    if ext in text_exts:
        text = data.decode("utf-8", errors="replace")
    else:
        extractor = getattr(legacy_core, "_extract_text", None)
        if callable(extractor):
            try:
                extracted, _used_ocr = extractor(path)
                text = str(extracted or "")
            except Exception:
                text = ""
        if not text:
            text = data.decode("utf-8", errors="replace")
    text = text.replace("\x00", " ").replace("\r", " ").strip()
    return text[:8000]


def ingest_one(
    tenant_id: str,
    source_kind: str,
    file_bytes: bytes,
    metadata_min: dict[str, str],
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    tenant = _tenant(tenant_id)
    if source_kind == "email":
        return knowledge_email_ingest_eml(
            tenant,
            actor_user_id,
            file_bytes,
            filename_hint=metadata_min.get("file_name"),
        )
    if source_kind == "calendar":
        return knowledge_ics_ingest(
            tenant,
            actor_user_id,
            file_bytes,
            filename_hint=metadata_min.get("file_name"),
        )
    if source_kind == "document":
        path = Path(metadata_min.get("path") or "")
        source_ref = f"document:{metadata_min.get('path_hash', '')}"
        body = _extract_document_text(path, file_bytes)
        title = metadata_min.get("file_name") or path.name or "document"
        return knowledge_document_ingest(
            tenant,
            actor_user_id,
            source_ref=source_ref,
            title=title,
            body=body,
            tags="source_scan",
        )
    raise ValueError("unknown_type")


def _classify_exc(exc: Exception) -> tuple[str, str]:
    if isinstance(exc, PermissionError):
        return "skipped_read_only", "read_only"
    if isinstance(exc, ConfigError):
        return "ingest_failed", "config_error"
    if isinstance(exc, ValueError):
        code = str(exc)
        if code == "policy_blocked":
            return "skipped_policy", code
        if code == "payload_too_large":
            return "skipped_limits", code
        if code in {"empty_file", "parse_error", "redacted_empty", "unknown_type"}:
            return "ingest_failed", code
        if code == "read_only":
            return "skipped_read_only", code
        return "ingest_failed", code or "validation_error"
    return "ingest_failed", "ingest_exception"


def _collect_candidates(cfg: dict[str, Any]) -> list[tuple[str, Path]]:
    out: list[tuple[str, Path]] = []

    docs_dir = _clean_dir(cfg.get("documents_inbox_dir"))
    email_dir = _clean_dir(cfg.get("email_inbox_dir"))
    cal_dir = _clean_dir(cfg.get("calendar_inbox_dir"))

    if docs_dir:
        root = Path(docs_dir)
        for fp in _iter_files(root):
            if fp.suffix.lower() in DOCUMENT_EXTS:
                out.append(("document", fp))

    if email_dir:
        root = Path(email_dir)
        files = _maildir_files(root) if _looks_maildir(root) else _iter_files(root)
        for fp in files:
            if _looks_maildir(root) or fp.suffix.lower() in EMAIL_EXTS:
                out.append(("email", fp))

    if cal_dir:
        root = Path(cal_dir)
        for fp in _iter_files(root):
            if fp.suffix.lower() in CALENDAR_EXTS:
                out.append(("calendar", fp))

    dedup: dict[tuple[str, str], tuple[str, Path]] = {}
    for kind, path in out:
        key = (kind, _normalize_path(str(path)))
        dedup[key] = (kind, path)
    return [dedup[k] for k in sorted(dedup.keys(), key=lambda x: (x[0], x[1]))]


def scan_sources_once(
    tenant_id: str,
    actor_user_id: str | None = None,
    budget_ms: int = DEFAULT_BUDGET_MS,
) -> dict[str, Any]:
    tenant = _tenant(tenant_id)
    budget = max(100, min(int(budget_ms), 30_000))
    started = time.monotonic()

    summary: dict[str, Any] = {
        "tenant_id": tenant,
        "ok": True,
        "scanned": 0,
        "discovered": 0,
        "ingested_ok": 0,
        "failed": 0,
        "skipped_policy": 0,
        "skipped_limits": 0,
        "skipped_read_only": 0,
        "skipped_unknown": 0,
        "skipped_unchanged": 0,
        "budget_exhausted": False,
        "max_files_reached": False,
    }

    if _is_read_only():
        summary["ok"] = True
        summary["skipped_read_only"] = 1
        summary["reason"] = "read_only"
        summary["duration_ms"] = int(round((time.monotonic() - started) * 1000))
        return summary

    cfg = source_watch_config_get(tenant, create_if_missing=True)
    if int(cfg.get("enabled") or 0) != 1:
        summary["reason"] = "disabled"
        summary["duration_ms"] = int(round((time.monotonic() - started) * 1000))
        return summary

    max_files = max(
        1, min(int(cfg.get("max_files_per_scan") or DEFAULT_MAX_FILES), MAX_FILES_HARD)
    )
    candidates = _collect_candidates(cfg)

    for source_kind, path in candidates:
        if summary["scanned"] >= max_files:
            summary["max_files_reached"] = True
            break
        elapsed_ms = int((time.monotonic() - started) * 1000)
        if elapsed_ms > budget:
            summary["budget_exhausted"] = True
            break

        summary["scanned"] += 1
        try:
            st = path.stat()
        except Exception:
            summary["failed"] += 1
            summary["ok"] = False
            continue

        path_hash = hmac_path_hash(str(path))
        fingerprint = _fingerprint(path, st)
        source_file = _touch_source_file(tenant, source_kind, path_hash, fingerprint)
        if source_file["is_new"]:
            summary["discovered"] += 1

        if not source_file["changed"] and str(source_file.get("status")) == "ingested":
            summary["skipped_unchanged"] += 1
            continue

        max_bytes = _kind_limit(source_kind, cfg)
        if int(st.st_size) > max_bytes:
            _record_outcome(
                tenant_id=tenant,
                source_file_id=str(source_file["id"]),
                source_kind=source_kind,
                path_hash=path_hash,
                action="skipped_limits",
                detail_code="oversize",
                actor_user_id=actor_user_id,
            )
            summary["skipped_limits"] += 1
            continue

        try:
            data = path.read_bytes()
        except Exception:
            _record_outcome(
                tenant_id=tenant,
                source_file_id=str(source_file["id"]),
                source_kind=source_kind,
                path_hash=path_hash,
                action="ingest_failed",
                detail_code="read_error",
                actor_user_id=actor_user_id,
            )
            summary["failed"] += 1
            summary["ok"] = False
            continue

        action = "ingest_ok"
        detail_code = "ok"
        try:
            ingest_one(
                tenant,
                source_kind,
                data,
                metadata_min={
                    "path": str(path),
                    "path_hash": path_hash,
                    "file_name": path.name,
                },
                actor_user_id=actor_user_id,
            )
        except Exception as exc:
            action, detail_code = _classify_exc(exc)

        _record_outcome(
            tenant_id=tenant,
            source_file_id=str(source_file["id"]),
            source_kind=source_kind,
            path_hash=path_hash,
            action=action,
            detail_code=detail_code,
            actor_user_id=actor_user_id,
        )

        if action == "ingest_ok":
            summary["ingested_ok"] += 1
        elif action == "skipped_policy":
            summary["skipped_policy"] += 1
        elif action == "skipped_limits":
            summary["skipped_limits"] += 1
        elif action == "skipped_read_only":
            summary["skipped_read_only"] += 1
        elif action.startswith("skipped"):
            summary["skipped_unknown"] += 1
        else:
            summary["failed"] += 1
            summary["ok"] = False

    summary["duration_ms"] = int(round((time.monotonic() - started) * 1000))
    return summary
