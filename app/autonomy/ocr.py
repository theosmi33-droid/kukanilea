from __future__ import annotations

import os
import re
import shutil
import sqlite3
import subprocess
import time
import uuid
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

from flask import current_app, has_app_context

import kukanilea_core_v3_fixed as legacy_core
from app.event_id_map import entity_id_int
from app.eventlog.core import event_append
from app.knowledge import knowledge_policy_get, knowledge_redact_text

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
DEFAULT_OCR_MAX_BYTES = 10 * 1024 * 1024
DEFAULT_OCR_TIMEOUT_SEC = 30
DEFAULT_OCR_MAX_CHARS = 200_000
DEFAULT_OCR_LANG = "eng"
MAX_DB_BODY_CHARS = 8000
LANG_RE = re.compile(r"^[a-z0-9_+]{2,32}$")
TESSERACT_ALLOWED_DIRS = (
    Path("/usr/bin"),
    Path("/usr/local/bin"),
    Path("/opt/homebrew/bin"),
)


def _tenant(tenant_id: str) -> str:
    tenant = legacy_core._effective_tenant(tenant_id)  # type: ignore[attr-defined]
    if not tenant:
        tenant = legacy_core._effective_tenant(legacy_core.TENANT_DEFAULT)  # type: ignore[attr-defined]
    return tenant or "default"


def _db() -> sqlite3.Connection:
    return legacy_core._db()  # type: ignore[attr-defined]


def _run_write_txn(fn):
    return legacy_core._run_write_txn(fn)  # type: ignore[attr-defined]


def _read_row(sql: str, params: tuple[Any, ...]) -> dict[str, Any] | None:
    with legacy_core._DB_LOCK:  # type: ignore[attr-defined]
        con = _db()
        try:
            row = con.execute(sql, params).fetchone()
            return dict(row) if row else None
        finally:
            con.close()


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


def _cfg_int(name: str, default: int, min_value: int, max_value: int) -> int:
    raw: Any = None
    if has_app_context():
        raw = current_app.config.get(name)
    if raw in (None, ""):
        raw = os.environ.get(name, "")
    try:
        value = int(raw) if raw not in (None, "") else default
    except Exception:
        value = default
    return max(min_value, min(value, max_value))


def _cfg_lang() -> str:
    raw: Any = None
    if has_app_context():
        raw = current_app.config.get("AUTONOMY_OCR_LANG")
    if raw in (None, ""):
        raw = os.environ.get("AUTONOMY_OCR_LANG", DEFAULT_OCR_LANG)
    value = str(raw or DEFAULT_OCR_LANG).strip().lower()
    if LANG_RE.match(value):
        return value
    return DEFAULT_OCR_LANG


def ocr_allowed(tenant_id: str) -> bool:
    tenant = _tenant(tenant_id)
    policy = knowledge_policy_get(tenant)
    return bool(int(policy.get("allow_ocr", 0)))


def is_supported_image_path(path: Path | str) -> bool:
    return Path(str(path)).suffix.lower() in IMAGE_EXTS


def resolve_tesseract_bin() -> Path | None:
    location = shutil.which("tesseract")
    if not location:
        return None
    from_which = Path(location)
    if not from_which.is_absolute():
        return None

    def _is_allowlisted(candidate: Path) -> bool:
        for allowed_dir in TESSERACT_ALLOWED_DIRS:
            try:
                if candidate.is_relative_to(allowed_dir):
                    return True
            except AttributeError:
                if str(candidate).startswith(str(allowed_dir) + os.sep):
                    return True
        return False

    # Keep the original `which` location allowlisted even if it is a symlink into
    # a versioned cellar path.
    if _is_allowlisted(from_which):
        return from_which

    resolved = from_which.resolve()
    if not resolved.is_absolute():
        return None
    if _is_allowlisted(resolved):
        return resolved

    # Homebrew resolves symlinks to /opt/homebrew/Cellar/...; allow that target.
    cellar_root = Path("/opt/homebrew/Cellar")
    try:
        if resolved.is_relative_to(cellar_root):
            return from_which
    except AttributeError:
        if str(resolved).startswith(str(cellar_root) + os.sep):
            return from_which
    return None


def _event_emit(
    *,
    event_type: str,
    tenant_id: str,
    actor_user_id: str | None,
    source_file_id: str,
    data: dict[str, Any],
) -> None:
    def _tx(con: sqlite3.Connection) -> None:
        event_append(
            event_type=event_type,
            entity_type="source_file",
            entity_id=entity_id_int(source_file_id),
            payload={
                "schema_version": 1,
                "source": "autonomy/ocr",
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


def _job_create(tenant_id: str, source_file_id: str) -> str:
    job_id = _new_id()
    created_at = _now_iso()

    def _tx(con: sqlite3.Connection) -> None:
        con.execute(
            """
            INSERT INTO autonomy_ocr_jobs(
              id, tenant_id, source_file_id, status, started_at, finished_at,
              duration_ms, bytes_in, chars_out, error_code, created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                job_id,
                tenant_id,
                source_file_id,
                "pending",
                None,
                None,
                0,
                0,
                0,
                None,
                created_at,
            ),
        )

    _run_write_txn(_tx)
    return job_id


def _job_set_processing(job_id: str, tenant_id: str) -> str:
    started_at = _now_iso()

    def _tx(con: sqlite3.Connection) -> None:
        con.execute(
            """
            UPDATE autonomy_ocr_jobs
            SET status='processing', started_at=?, error_code=NULL
            WHERE tenant_id=? AND id=?
            """,
            (started_at, tenant_id, job_id),
        )

    _run_write_txn(_tx)
    return started_at


def _job_finish(
    *,
    tenant_id: str,
    job_id: str,
    status: str,
    error_code: str | None,
    duration_ms: int,
    bytes_in: int,
    chars_out: int,
) -> None:
    def _tx(con: sqlite3.Connection) -> None:
        con.execute(
            """
            UPDATE autonomy_ocr_jobs
            SET status=?, finished_at=?, duration_ms=?, bytes_in=?, chars_out=?, error_code=?
            WHERE tenant_id=? AND id=?
            """,
            (
                status,
                _now_iso(),
                int(duration_ms),
                int(bytes_in),
                int(chars_out),
                error_code,
                tenant_id,
                job_id,
            ),
        )

    _run_write_txn(_tx)


def _run_tesseract(
    image_path: Path,
    lang: str,
    timeout_sec: int,
    max_chars: int,
) -> tuple[str | None, str | None, int]:
    binary = resolve_tesseract_bin()
    if binary is None:
        return None, "tesseract_missing", 0
    cmd = [str(binary), str(image_path), "stdout", "-l", lang]
    try:
        proc = subprocess.run(  # noqa: S603
            cmd,
            capture_output=True,
            text=True,
            timeout=int(timeout_sec),
            check=False,
            shell=False,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        return None, "timeout", 0
    except Exception:
        return None, "failed", 0
    if int(proc.returncode or 0) != 0:
        return None, "failed", 0
    output = str(proc.stdout or "")
    truncated = 0
    if len(output) > max_chars:
        output = output[:max_chars]
        truncated = 1
    return output, None, truncated


def _store_ocr_chunk(
    *,
    tenant_id: str,
    source_file_id: str,
    actor_user_id: str | None,
    redacted_text: str,
) -> tuple[str, int]:
    source_ref = f"ocr:{source_file_id}"
    chunk_id = _new_id()
    title = f"OCR Source {source_file_id[:8]}"
    tags = "ocr"
    content_hash = sha256(redacted_text.encode("utf-8")).hexdigest()
    now = _now_iso()

    def _tx(con: sqlite3.Connection) -> tuple[str, int]:
        row = con.execute(
            """
            SELECT id, chunk_id
            FROM knowledge_chunks
            WHERE tenant_id=? AND source_type='ocr' AND source_ref=? AND content_hash=?
            LIMIT 1
            """,
            (tenant_id, source_ref, content_hash),
        ).fetchone()
        if row:
            existing_chunk_id = str(row["chunk_id"])
            row_id = int(row["id"])
            con.execute(
                """
                UPDATE source_files
                SET ocr_knowledge_chunk_id=?
                WHERE tenant_id=? AND id=?
                """,
                (existing_chunk_id, tenant_id, source_file_id),
            )
            return existing_chunk_id, row_id

        cur = con.execute(
            """
            INSERT INTO knowledge_chunks(
              chunk_id, tenant_id, owner_user_id, source_type, source_ref,
              title, body, tags, content_hash, is_redacted, created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                chunk_id,
                tenant_id,
                actor_user_id or None,
                "ocr",
                source_ref,
                title,
                redacted_text,
                tags,
                content_hash,
                1,
                now,
                now,
            ),
        )
        row_id = int(cur.lastrowid or 0)
        try:
            con.execute(
                "INSERT INTO knowledge_fts(rowid, title, body, tags) VALUES (?,?,?,?)",
                (row_id, title, redacted_text, tags),
            )
        except Exception:
            con.execute(
                "INSERT OR REPLACE INTO knowledge_fts_fallback(rowid, title, body, tags) VALUES (?,?,?,?)",
                (row_id, title, redacted_text, tags),
            )
        con.execute(
            """
            UPDATE source_files
            SET ocr_knowledge_chunk_id=?
            WHERE tenant_id=? AND id=?
            """,
            (chunk_id, tenant_id, source_file_id),
        )
        event_append(
            event_type="knowledge_ocr_ingested",
            entity_type="knowledge_chunk",
            entity_id=row_id,
            payload={
                "schema_version": 1,
                "source": "autonomy/ocr",
                "actor_user_id": actor_user_id,
                "tenant_id": tenant_id,
                "data": {
                    "chunk_id": chunk_id,
                    "source_type": "ocr",
                    "source_file_id": source_file_id,
                },
            },
            con=con,
        )
        return chunk_id, row_id

    return _run_write_txn(_tx)


def submit_ocr_for_source_file(
    tenant_id: str,
    actor_user_id: str | None,
    source_file_id: str,
    abs_path: Path | str,
) -> dict[str, Any]:
    if _is_read_only():
        raise PermissionError("read_only")
    tenant = _tenant(tenant_id)
    source_file = str(source_file_id or "").strip()
    if not source_file:
        raise ValueError("validation_error")
    row = _read_row(
        "SELECT id FROM source_files WHERE tenant_id=? AND id=? LIMIT 1",
        (tenant, source_file),
    )
    if not row:
        raise ValueError("not_found")

    target = Path(str(abs_path))
    ext = target.suffix.lower()
    size_bytes = int(target.stat().st_size) if target.exists() else 0
    max_bytes = _cfg_int(
        "AUTONOMY_OCR_MAX_BYTES", DEFAULT_OCR_MAX_BYTES, 1, 100_000_000
    )
    timeout_sec = _cfg_int("AUTONOMY_OCR_TIMEOUT_SEC", DEFAULT_OCR_TIMEOUT_SEC, 1, 300)
    max_chars = _cfg_int("AUTONOMY_OCR_MAX_CHARS", DEFAULT_OCR_MAX_CHARS, 100, 500_000)
    lang = _cfg_lang()

    job_id = _job_create(tenant, source_file)

    if not ocr_allowed(tenant):
        _job_finish(
            tenant_id=tenant,
            job_id=job_id,
            status="skipped",
            error_code="policy_denied",
            duration_ms=0,
            bytes_in=size_bytes,
            chars_out=0,
        )
        _event_emit(
            event_type="autonomy_ocr_failed",
            tenant_id=tenant,
            actor_user_id=actor_user_id,
            source_file_id=source_file,
            data={
                "job_id": job_id,
                "source_file_id": source_file,
                "error_code": "policy_denied",
            },
        )
        return {
            "ok": False,
            "job_id": job_id,
            "status": "skipped",
            "error_code": "policy_denied",
        }

    if ext == ".pdf":
        _job_finish(
            tenant_id=tenant,
            job_id=job_id,
            status="failed",
            error_code="pdf_not_supported",
            duration_ms=0,
            bytes_in=size_bytes,
            chars_out=0,
        )
        _event_emit(
            event_type="autonomy_ocr_failed",
            tenant_id=tenant,
            actor_user_id=actor_user_id,
            source_file_id=source_file,
            data={
                "job_id": job_id,
                "source_file_id": source_file,
                "error_code": "pdf_not_supported",
            },
        )
        return {
            "ok": False,
            "job_id": job_id,
            "status": "failed",
            "error_code": "pdf_not_supported",
        }

    if ext not in IMAGE_EXTS:
        _job_finish(
            tenant_id=tenant,
            job_id=job_id,
            status="failed",
            error_code="unsupported_ext",
            duration_ms=0,
            bytes_in=size_bytes,
            chars_out=0,
        )
        _event_emit(
            event_type="autonomy_ocr_failed",
            tenant_id=tenant,
            actor_user_id=actor_user_id,
            source_file_id=source_file,
            data={
                "job_id": job_id,
                "source_file_id": source_file,
                "error_code": "unsupported_ext",
            },
        )
        return {
            "ok": False,
            "job_id": job_id,
            "status": "failed",
            "error_code": "unsupported_ext",
        }

    if size_bytes <= 0 or not target.exists():
        _job_finish(
            tenant_id=tenant,
            job_id=job_id,
            status="failed",
            error_code="missing_file",
            duration_ms=0,
            bytes_in=size_bytes,
            chars_out=0,
        )
        _event_emit(
            event_type="autonomy_ocr_failed",
            tenant_id=tenant,
            actor_user_id=actor_user_id,
            source_file_id=source_file,
            data={
                "job_id": job_id,
                "source_file_id": source_file,
                "error_code": "missing_file",
            },
        )
        return {
            "ok": False,
            "job_id": job_id,
            "status": "failed",
            "error_code": "missing_file",
        }

    if size_bytes > max_bytes:
        _job_finish(
            tenant_id=tenant,
            job_id=job_id,
            status="failed",
            error_code="too_large",
            duration_ms=0,
            bytes_in=size_bytes,
            chars_out=0,
        )
        _event_emit(
            event_type="autonomy_ocr_failed",
            tenant_id=tenant,
            actor_user_id=actor_user_id,
            source_file_id=source_file,
            data={
                "job_id": job_id,
                "source_file_id": source_file,
                "error_code": "too_large",
            },
        )
        return {
            "ok": False,
            "job_id": job_id,
            "status": "failed",
            "error_code": "too_large",
        }

    _job_set_processing(job_id, tenant)
    _event_emit(
        event_type="autonomy_ocr_started",
        tenant_id=tenant,
        actor_user_id=actor_user_id,
        source_file_id=source_file,
        data={"job_id": job_id, "source_file_id": source_file},
    )

    started = time.monotonic()
    text_out, error_code, truncated = _run_tesseract(
        target, lang=lang, timeout_sec=timeout_sec, max_chars=max_chars
    )
    duration_ms = int(round((time.monotonic() - started) * 1000))
    if error_code:
        _job_finish(
            tenant_id=tenant,
            job_id=job_id,
            status="failed",
            error_code=error_code,
            duration_ms=duration_ms,
            bytes_in=size_bytes,
            chars_out=0,
        )
        _event_emit(
            event_type="autonomy_ocr_failed",
            tenant_id=tenant,
            actor_user_id=actor_user_id,
            source_file_id=source_file,
            data={
                "job_id": job_id,
                "source_file_id": source_file,
                "error_code": error_code,
            },
        )
        return {
            "ok": False,
            "job_id": job_id,
            "status": "failed",
            "error_code": error_code,
        }

    redacted = knowledge_redact_text(
        text_out or "", max_len=min(max_chars, MAX_DB_BODY_CHARS)
    )
    if not redacted:
        _job_finish(
            tenant_id=tenant,
            job_id=job_id,
            status="failed",
            error_code="redacted_empty",
            duration_ms=duration_ms,
            bytes_in=size_bytes,
            chars_out=0,
        )
        _event_emit(
            event_type="autonomy_ocr_failed",
            tenant_id=tenant,
            actor_user_id=actor_user_id,
            source_file_id=source_file,
            data={
                "job_id": job_id,
                "source_file_id": source_file,
                "error_code": "redacted_empty",
            },
        )
        return {
            "ok": False,
            "job_id": job_id,
            "status": "failed",
            "error_code": "redacted_empty",
        }

    chunk_id, _row_id = _store_ocr_chunk(
        tenant_id=tenant,
        source_file_id=source_file,
        actor_user_id=actor_user_id,
        redacted_text=redacted,
    )
    chars_out = len(redacted)
    _job_finish(
        tenant_id=tenant,
        job_id=job_id,
        status="done",
        error_code=None,
        duration_ms=duration_ms,
        bytes_in=size_bytes,
        chars_out=chars_out,
    )
    _event_emit(
        event_type="autonomy_ocr_done",
        tenant_id=tenant,
        actor_user_id=actor_user_id,
        source_file_id=source_file,
        data={
            "job_id": job_id,
            "source_file_id": source_file,
            "duration_ms": duration_ms,
            "chars_out": chars_out,
            "truncated": int(truncated),
        },
    )
    return {
        "ok": True,
        "job_id": job_id,
        "status": "done",
        "source_file_id": source_file,
        "ocr_knowledge_chunk_id": chunk_id,
        "chars_out": chars_out,
        "duration_ms": duration_ms,
        "truncated": int(truncated),
    }


def recent_ocr_jobs(tenant_id: str, limit: int = 10) -> list[dict[str, Any]]:
    tenant = _tenant(tenant_id)
    lim = max(1, min(int(limit), 100))
    with legacy_core._DB_LOCK:  # type: ignore[attr-defined]
        con = _db()
        try:
            rows = con.execute(
                """
                SELECT id, tenant_id, source_file_id, status, started_at, finished_at,
                       duration_ms, bytes_in, chars_out, error_code, created_at
                FROM autonomy_ocr_jobs
                WHERE tenant_id=?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (tenant, lim),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            con.close()


def ocr_stats_24h(tenant_id: str) -> dict[str, int]:
    tenant = _tenant(tenant_id)
    since = (_now_utc() - timedelta(days=1)).isoformat(timespec="seconds")
    with legacy_core._DB_LOCK:  # type: ignore[attr-defined]
        con = _db()
        try:
            rows = con.execute(
                """
                SELECT status, COUNT(*) AS c
                FROM autonomy_ocr_jobs
                WHERE tenant_id=? AND created_at>=?
                GROUP BY status
                ORDER BY status ASC
                """,
                (tenant, since),
            ).fetchall()
        finally:
            con.close()
    out = {"done": 0, "failed": 0, "skipped": 0, "processing": 0, "pending": 0}
    for row in rows:
        status = str(row["status"] or "")
        if status in out:
            out[status] = int(row["c"] or 0)
    out["total"] = sum(out.values())
    return out
