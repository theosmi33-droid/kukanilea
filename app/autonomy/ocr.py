from __future__ import annotations

import contextlib
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal, Mapping

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
TESSERACT_ALLOWLIST_ENV = "KUKANILEA_TESSERACT_ALLOWED_PREFIXES"
TESSERACT_BIN_ENV = "AUTONOMY_OCR_TESSERACT_BIN"
TESSDATA_DIR_ENV = "AUTONOMY_OCR_TESSDATA_DIR"
TESSDATA_ERROR_RE = re.compile(
    r"(error opening data file|failed loading language|could not initialize tesseract)",
    re.IGNORECASE,
)
CONFIG_FILE_ERROR_RE = re.compile(
    r"(read_params_file|can.?t open config|could not open config)",
    re.IGNORECASE,
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


def _cfg_tessdata_dir() -> str | None:
    raw: Any = None
    if has_app_context():
        raw = current_app.config.get(TESSDATA_DIR_ENV)
    if raw in (None, ""):
        raw = os.environ.get(TESSDATA_DIR_ENV, "")
    value = str(raw or "").strip()
    return value or None


def _default_tesseract_allowed_prefixes(
    platform_name: str | None = None,
) -> tuple[str, ...]:
    detected = str(platform_name or sys.platform).casefold()
    if detected.startswith("darwin"):
        return ("/usr/bin", "/usr/local/bin", "/opt/homebrew")
    if detected.startswith("linux"):
        return ("/usr/bin", "/usr/local/bin", "/home/linuxbrew/.linuxbrew")
    if detected.startswith("win"):
        return (
            r"C:\Program Files\Tesseract-OCR",
            r"C:\Program Files (x86)\Tesseract-OCR",
        )
    return ("/usr/bin", "/usr/local/bin")


def _is_safe_tesseract_prefix(path: Path) -> bool:
    try:
        normalized = Path(os.path.normpath(str(path)))
    except Exception:
        return False
    if not normalized.is_absolute():
        return False
    anchor = str(normalized.anchor or "")
    # Reject filesystem root prefixes.
    if str(normalized) == anchor:
        return False
    if os.name == "nt":
        lowered = str(normalized).replace("/", "\\").strip().casefold()
        if lowered in {r"c:\\", r"d:\\", r"e:\\", r"\\"}:
            return False
    else:
        if str(normalized) == "/":
            return False
    return True


def _allowed_tesseract_prefixes(
    *,
    platform_name: str | None = None,
    env: dict[str, str] | None = None,
) -> tuple[Path, ...]:
    prefixes: list[Path] = []
    seen: set[str] = set()

    def _add(raw: str | Path | None) -> None:
        text = str(raw or "").strip()
        if not text:
            return
        path = Path(text).expanduser()
        if not _is_safe_tesseract_prefix(path):
            return
        normalized = Path(os.path.normpath(str(path)))
        key = str(normalized).casefold()
        if key in seen:
            return
        seen.add(key)
        prefixes.append(normalized)

    for item in _default_tesseract_allowed_prefixes(platform_name):
        _add(item)

    env_map = env if env is not None else os.environ
    extra_raw = str(env_map.get(TESSERACT_ALLOWLIST_ENV, "") or "")
    if extra_raw:
        for item in extra_raw.split(os.pathsep):
            _add(item)
    return tuple(prefixes)


def _path_within_prefix(candidate: Path, prefix: Path) -> bool:
    try:
        return candidate.is_relative_to(prefix)
    except AttributeError:
        prefix_str = str(prefix)
        candidate_str = str(candidate)
        return candidate_str == prefix_str or candidate_str.startswith(
            prefix_str + os.sep
        )


def classify_tesseract_path(
    path: str | Path,
    *,
    platform_name: str | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    candidate = Path(str(path or "")).expanduser()
    candidate_abs = Path(os.path.abspath(str(candidate))) if str(candidate) else None
    prefixes = _allowed_tesseract_prefixes(platform_name=platform_name, env=env)
    allowed_prefixes = [str(p) for p in prefixes]
    result: dict[str, Any] = {
        "exists": False,
        "executable": False,
        "allowlisted": False,
        "reason": "tesseract_missing",
        "allowlist_reason": "path_missing_or_not_executable",
        "allowed_prefixes": allowed_prefixes,
        "normalized": str(candidate_abs) if candidate_abs is not None else None,
        "resolved": None,
    }

    if candidate_abs is None:
        return result
    exists = candidate_abs.exists() and candidate_abs.is_file()
    executable = exists and os.access(candidate_abs, os.X_OK)
    result["exists"] = bool(exists)
    result["executable"] = bool(executable)
    if not executable:
        return result

    resolved = Path(os.path.realpath(str(candidate_abs)))
    result["resolved"] = str(resolved)

    for prefix in prefixes:
        if _path_within_prefix(candidate_abs, prefix) or _path_within_prefix(
            resolved, prefix
        ):
            result["allowlisted"] = True
            result["reason"] = "ok"
            result["allowlist_reason"] = "matched_prefix"
            return result

    result["reason"] = "tesseract_not_allowlisted"
    result["allowlist_reason"] = "outside_allowed_prefixes"
    return result


@dataclass(frozen=True)
class ResolvedTesseractBin:
    requested: str | None
    resolved_path: str | None
    exists: bool
    executable: bool
    allowlisted: bool
    allowlist_reason: str | None
    allowed_prefixes: tuple[str, ...]
    resolution_source: Literal["explicit", "env", "path", "none"]
    os_error_errno: int | None = None
    os_error_type: str | None = None


def resolve_tesseract_binary(
    requested_bin: str | None = None,
    env: Mapping[str, str] | None = None,
    *,
    platform_name: str | None = None,
) -> ResolvedTesseractBin:
    env_map = dict(os.environ)
    if env:
        env_map.update(dict(env))

    requested = str(requested_bin or "").strip() or None
    env_requested = str(env_map.get(TESSERACT_BIN_ENV, "") or "").strip() or None
    cfg_requested = None
    if has_app_context():
        cfg_requested = (
            str(current_app.config.get(TESSERACT_BIN_ENV, "") or "").strip() or None
        )
    preferred_from_runtime = env_requested or cfg_requested

    if requested:
        candidate = requested
        source: Literal["explicit", "env", "path", "none"] = "explicit"
    elif preferred_from_runtime:
        candidate = preferred_from_runtime
        source = "env"
    else:
        try:
            candidate = shutil.which("tesseract", path=env_map.get("PATH"))
        except TypeError:
            candidate = shutil.which("tesseract")
        source = "path" if candidate else "none"

    if not candidate:
        prefixes = _allowed_tesseract_prefixes(platform_name=platform_name, env=env_map)
        return ResolvedTesseractBin(
            requested=requested,
            resolved_path=None,
            exists=False,
            executable=False,
            allowlisted=False,
            allowlist_reason="path_missing_or_not_executable",
            allowed_prefixes=tuple(str(p) for p in prefixes),
            resolution_source="none",
        )

    classified = classify_tesseract_path(
        candidate,
        platform_name=platform_name,
        env=env_map,
    )
    return ResolvedTesseractBin(
        requested=requested,
        resolved_path=str(
            classified.get("resolved") or classified.get("normalized") or candidate
        ),
        exists=bool(classified.get("exists")),
        executable=bool(classified.get("executable")),
        allowlisted=bool(classified.get("allowlisted")),
        allowlist_reason=str(classified.get("allowlist_reason") or "") or None,
        allowed_prefixes=tuple(
            str(item) for item in list(classified.get("allowed_prefixes") or [])
        ),
        resolution_source=source,
    )


def ocr_allowed(tenant_id: str) -> bool:
    tenant = _tenant(tenant_id)
    policy = knowledge_policy_get(tenant)
    return bool(int(policy.get("allow_ocr", 0)))


def is_supported_image_path(path: Path | str) -> bool:
    return Path(str(path)).suffix.lower() in IMAGE_EXTS


def resolve_tesseract_bin(
    requested_bin: str | None = None,
    env: Mapping[str, str] | None = None,
) -> Path | None:
    resolved = resolve_tesseract_binary(requested_bin=requested_bin, env=env)
    if not (resolved.exists and resolved.executable and resolved.allowlisted):
        return None
    return Path(str(resolved.resolved_path or "")).expanduser()


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
    tessdata_dir: str | None = None,
    tesseract_bin_override: str | None = None,
    *,
    allow_retry: bool = True,
) -> tuple[str | None, str | None, int, str | None]:
    from app.devtools.tesseract_probe import probe_tesseract

    resolved = resolve_tesseract_binary(requested_bin=tesseract_bin_override)
    if not resolved.exists or not resolved.executable:
        return None, "tesseract_missing", 0, None
    if not resolved.allowlisted:
        return None, "tesseract_not_allowlisted", 0, None
    binary = Path(str(resolved.resolved_path or "")).expanduser()
    if not str(binary):
        return None, "tesseract_missing", 0, None

    def _sanitize_stderr(text: str | None) -> str | None:
        if not text:
            return None
        out = re.sub(r"/[^\s\"']+", "<path>", str(text))
        out = out.replace("\x00", "").replace("\r", " ").replace("\n", " ").strip()
        if len(out) > 400:
            out = out[-400:]
        return out or None

    def _classify(stderr_text: str | None) -> str:
        lower = str(stderr_text or "").casefold()
        if CONFIG_FILE_ERROR_RE.search(lower):
            return "config_file_missing"
        if "error opening data file" in lower:
            return "tessdata_missing"
        if (
            "failed loading language" in lower
            or "could not initialize tesseract" in lower
        ):
            return "language_missing"
        return "tesseract_failed"

    def _build_tesseract_cmd(
        *,
        binary_path: Path,
        image: Path,
        lang_code: str,
        tess_dir: str | None,
    ) -> list[str]:
        cmd = [str(binary_path), str(image), "stdout", "-l", lang_code]
        if tess_dir:
            cmd.extend(["--tessdata-dir", str(tess_dir)])
        return cmd

    def _run_once(
        lang_code: str, tess_dir: str | None
    ) -> tuple[str | None, str | None, int, str | None]:
        cmd = _build_tesseract_cmd(
            binary_path=binary,
            image=image_path,
            lang_code=lang_code,
            tess_dir=tess_dir,
        )
        env_copy = dict(os.environ)
        if tess_dir:
            env_copy["TESSDATA_PREFIX"] = str(tess_dir)
        try:
            proc = subprocess.run(  # noqa: S603
                cmd,
                capture_output=True,
                text=True,
                timeout=int(timeout_sec),
                check=False,
                shell=False,
                stdin=subprocess.DEVNULL,
                env=env_copy,
            )
        except subprocess.TimeoutExpired:
            return None, "timeout", 0, "timeout"
        except (FileNotFoundError, OSError) as exc:
            errno = getattr(exc, "errno", None)
            errno_part = f"errno={errno};" if errno is not None else ""
            return (
                None,
                "tesseract_exec_failed",
                0,
                _sanitize_stderr(f"{errno_part}{type(exc).__name__}"),
            )
        except Exception as exc:
            return None, "tesseract_failed", 0, type(exc).__name__
        if int(proc.returncode or 0) != 0:
            stderr = str(proc.stderr or proc.stdout or "")
            return None, _classify(stderr), 0, _sanitize_stderr(stderr)
        output = str(proc.stdout or "")
        truncated = 0
        if len(output) > max_chars:
            output = output[:max_chars]
            truncated = 1
        return output, None, truncated, None

    text_out, error_code, truncated, stderr_tail = _run_once(lang, tessdata_dir)
    if allow_retry and error_code in {"tessdata_missing", "language_missing"}:
        probe = probe_tesseract(
            bin_path=str(binary),
            tessdata_dir=tessdata_dir,
            preferred_langs=[lang],
            timeout_s=min(max(1, int(timeout_sec)), 5),
        )
        retry_lang = str(
            probe.get("lang_selected") or probe.get("lang_used") or ""
        ).strip()
        retry_tess = (
            str(
                probe.get("tessdata_prefix")
                or probe.get("tessdata_dir_used")
                or probe.get("tessdata_dir")
                or ""
            ).strip()
            or None
        )
        if not retry_lang and str(probe.get("reason") or "") == "language_missing":
            for candidate in list(probe.get("langs") or []):
                token = str(candidate).strip().lower()
                if token and token != "osd":
                    retry_lang = token
                    break
        if retry_lang and (retry_lang != lang or retry_tess != tessdata_dir):
            retry_text, retry_error, retry_truncated, retry_stderr = _run_once(
                retry_lang,
                retry_tess,
            )
            if retry_error is None:
                return retry_text, None, retry_truncated, retry_stderr
            error_code = retry_error
            stderr_tail = retry_stderr
    return text_out, error_code, truncated, stderr_tail


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
    *,
    lang_override: str | None = None,
    tessdata_dir: str | None = None,
    tesseract_bin_override: str | None = None,
    allow_retry: bool = True,
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
    effective_bin = str(tesseract_bin_override or "").strip()
    effective_tessdata_dir = str(tessdata_dir or _cfg_tessdata_dir() or "").strip()
    lang = str(lang_override or _cfg_lang()).strip().lower()
    if not LANG_RE.match(lang):
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

    job_resolution = resolve_tesseract_binary(requested_bin=effective_bin or None)
    started = time.monotonic()
    text_out, error_code, truncated, _stderr_tail = _run_tesseract(
        target,
        lang=lang,
        timeout_sec=timeout_sec,
        max_chars=max_chars,
        tessdata_dir=effective_tessdata_dir or None,
        tesseract_bin_override=effective_bin or None,
        allow_retry=allow_retry,
    )
    duration_ms = int(round((time.monotonic() - started) * 1000))
    if error_code:
        exec_errno: int | None = None
        if error_code == "tesseract_exec_failed" and str(_stderr_tail or "").strip():
            match = re.search(r"errno=(\d+)", str(_stderr_tail))
            if match:
                with contextlib.suppress(Exception):
                    exec_errno = int(match.group(1))
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
            "stderr_tail": str(_stderr_tail or "") or None,
            "exec_errno": exec_errno,
            "tesseract_bin_used": job_resolution.resolved_path,
            "tesseract_allowlisted": bool(job_resolution.allowlisted),
            "tesseract_allowlist_reason": job_resolution.allowlist_reason,
            "tesseract_resolution_source": job_resolution.resolution_source,
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
        "tesseract_bin_used": job_resolution.resolved_path,
        "tesseract_allowlisted": bool(job_resolution.allowlisted),
        "tesseract_allowlist_reason": job_resolution.allowlist_reason,
        "tesseract_resolution_source": job_resolution.resolution_source,
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
