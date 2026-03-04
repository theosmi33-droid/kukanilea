"""
app/core/upload_pipeline.py
Safe file upload pipeline processing and OCR auto-learning helpers.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, List, Optional, Tuple

from app.config import Config

logger = logging.getLogger("kukanilea.upload_pipeline")

ALLOWED_EXTENSIONS = {
    ".pdf", ".png", ".jpg", ".jpeg", ".txt", ".md", ".csv", ".xlsx", ".tif", ".tiff"
}
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
INGESTION_TARGET_SECONDS = float(os.environ.get("KUKANILEA_INGESTION_TARGET_SECONDS", "3.0"))
MALWARE_SCAN_TIMEOUT_SECONDS = float(os.environ.get("KUKANILEA_CLAMAV_TIMEOUT_SECONDS", "4"))
MAX_HASH_LINES = 40
MAX_HASH_CHARS = 2400
STREAM_CHUNK_SIZE = 1024 * 1024


class UploadErrorCode(Enum):
    CLEAN = "CLEAN"
    CLEAN_UNSCANNED = "CLEAN_UNSCANNED"
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    UNSUPPORTED_EXTENSION = "UNSUPPORTED_EXTENSION"
    INFECTED = "INFECTED"
    CLAMAV_UNAVAILABLE = "CLAMAV_UNAVAILABLE"
    PIPELINE_ERROR = "PIPELINE_ERROR"


@dataclass
class UploadResult:
    success: bool
    file_hash: Optional[str] = None
    error_code: Optional[UploadErrorCode] = None
    error_message: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def __iter__(self):
        # Compatibility with (bool, str) return pattern
        yield self.success
        if self.success:
            yield self.file_hash
        else:
            yield self.error_message or "Ein unbekannter Fehler ist aufgetreten."


_ERROR_MESSAGES = {
    UploadErrorCode.CLEAN: "Datei ist sauber.",
    UploadErrorCode.CLEAN_UNSCANNED: "Datei wurde ohne Virenscan akzeptiert.",
    UploadErrorCode.FILE_NOT_FOUND: "Datei wurde nicht gefunden.",
    UploadErrorCode.FILE_TOO_LARGE: "Datei ist zu gross. Bitte reduzieren Sie die Dateigroesse.",
    UploadErrorCode.UNSUPPORTED_EXTENSION: "Dateityp wird nicht unterstuetzt.",
    UploadErrorCode.INFECTED: "Sicherheitsrisiko erkannt. Datei wurde blockiert.",
    UploadErrorCode.CLAMAV_UNAVAILABLE: "Virenscan derzeit nicht verfuegbar. Bitte versuchen Sie es spaeter erneut.",
    UploadErrorCode.PIPELINE_ERROR: "Ein interner Fehler ist aufgetreten.",
}

_CORRECTION_FIELDS: Tuple[Tuple[Tuple[str, ...], str, str], ...] = (
    (("doctype_suggested",), "doctype", "doctype"),
    (("kdnr_suggested", "kdnr_ranked"), "kdnr", "kdnr"),
    (("doc_date_suggested",), "document_date", "document_date"),
    (("name_suggestions",), "name", "name"),
    (("addr_suggestions",), "addr", "address"),
    (("plzort_suggestions",), "plzort", "plzort"),
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _first_suggestion(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        if not value:
            return ""
        first = value[0]
        if isinstance(first, (list, tuple)):
            return str(first[0] or "")
        return str(first or "")
    return str(value or "")


def _safe_unlink(file_path: Path) -> None:
    try:
        file_path.unlink()
    except Exception as exc:
        logger.warning("Rejected upload could not be deleted (%s): %s", file_path.name, exc)


def write_dead_letter_marker(
    file_path: Path,
    tenant_id: str,
    reason: str,
    context: Optional[Dict[str, Any]] = None,
) -> None:
    try:
        root = Path(__file__).resolve().parents[2]
        dead_dir = root / "quarantine" / "dead_letter_uploads"
        dead_dir.mkdir(parents=True, exist_ok=True)
        marker = dead_dir / f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}__{file_path.name}.json"
        marker.write_text(
            json.dumps(
                {
                    "tenant_id": tenant_id,
                    "file_name": file_path.name,
                    "reason": reason,
                    "created_at": _utc_now(),
                    "context": context or {},
                },
                ensure_ascii=True,
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception as exc:
        logger.warning("Could not write dead-letter marker for %s: %s", file_path.name, exc)


def _write_dead_letter(file_path: Path, tenant_id: str, reason: str) -> None:
    write_dead_letter_marker(file_path, tenant_id, reason)


def save_upload_stream(file_storage: Any, dest: Path, max_size: int = MAX_FILE_SIZE) -> int:
    """
    Persist Flask FileStorage stream in bounded chunks.
    Raises ValueError("file_too_large") if max_size is exceeded.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    stream = getattr(file_storage, "stream", None)
    if stream is None:
        raise ValueError("invalid_stream")

    with dest.open("wb") as handle:
        while True:
            chunk = stream.read(STREAM_CHUNK_SIZE)
            if not chunk:
                break
            written += len(chunk)
            if written > max_size:
                raise ValueError("file_too_large")
            handle.write(chunk)

    return written


def _audit_scan_event(file_path: Path, tenant_id: str, status: str, details: str = "") -> None:
    try:
        from app.core.audit import vault_store_evidence

        payload = {
            "original_filename": file_path.name,
            "size_bytes": file_path.stat().st_size if file_path.exists() else 0,
            "scan_status": status,
        }
        if details:
            payload["scan_details"] = details[:180]
        vault_store_evidence(
            doc_id=file_path.name,
            tenant_id=tenant_id,
            metadata_hash="",
            payload=payload,
        )
    except Exception as exc:
        logger.warning("Audit event for %s failed: %s", file_path.name, exc)


def _scan_malware(file_path: Path) -> Tuple[bool, UploadErrorCode]:
    """
    Mandatory ClamAV gate.
    Returns: (is_clean, UploadErrorCode)
    """
    try:
        import pyclamd

        cd = pyclamd.ClamdUnixSocket()
        if not cd.ping():
            if _clamav_optional_enabled():
                return True, UploadErrorCode.CLAMAV_UNAVAILABLE
            return False, UploadErrorCode.CLAMAV_UNAVAILABLE
        
        result = cd.scan_file(str(file_path))
        if result:
            logger.warning("Malware detected in %s: %s", file_path.name, result)
            return False, UploadErrorCode.INFECTED
        return True, UploadErrorCode.CLEAN
    except Exception as exc:
        logger.error("ClamAV scan error for %s: %s", file_path.name, exc)
        if _clamav_optional_enabled():
            return True, UploadErrorCode.CLAMAV_UNAVAILABLE
        return False, UploadErrorCode.CLAMAV_UNAVAILABLE


def _clamav_optional_enabled() -> bool:
    flag = str(os.environ.get("CLAMAV_OPTIONAL", "")).strip().lower() in {"1", "true", "yes", "on"}
    env = str(os.environ.get("KUKANILEA_ENV", os.environ.get("FLASK_ENV", ""))).strip().lower()
    in_test_runtime = bool(os.environ.get("PYTEST_CURRENT_TEST"))
    return flag and (in_test_runtime or env in {"test", "testing", "dev", "development", "ci"})


def _hash_file_sha256(file_path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def ensure_ocr_corrections_table(auth_db_path: Optional[Path] = None) -> None:
    db_path = Path(auth_db_path or Config.AUTH_DB)
    con = sqlite3.connect(str(db_path))
    try:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS ocr_corrections(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              tenant_id TEXT NOT NULL,
              document_id TEXT NOT NULL,
              field_name TEXT NOT NULL,
              corrected_value TEXT NOT NULL,
              layout_hash TEXT NOT NULL,
              created_at TEXT NOT NULL
            )
            """
        )
        con.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_ocr_corr_lookup
            ON ocr_corrections(tenant_id, layout_hash, field_name, created_at DESC)
            """
        )
        con.commit()
    finally:
        con.close()


def compute_layout_hash(text: str, file_name: str = "") -> str:
    """
    Deterministic layout hash based on stable text segments.
    """
    lines = []
    for raw in (text or "").splitlines():
        normalized = _normalize_text(raw).lower()
        if normalized:
            lines.append(normalized)
        if len(lines) >= MAX_HASH_LINES:
            break
    base = "\n".join(lines)[:MAX_HASH_CHARS]
    if not base:
        base = Path(file_name or "").suffix.lower()
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def collect_manual_corrections(
    original_suggestions: Dict[str, Any],
    final_answers: Dict[str, Any],
) -> List[Tuple[str, str]]:
    collected: List[Tuple[str, str]] = []
    for source_keys, answer_key, field_name in _CORRECTION_FIELDS:
        corrected = _normalize_text(final_answers.get(answer_key))
        if not corrected:
            continue
        source = ""
        for key in source_keys:
            source = _normalize_text(_first_suggestion(original_suggestions.get(key)))
            if source:
                break
        if source == corrected:
            continue
        collected.append((field_name, corrected))
    return collected


def store_ocr_corrections(
    tenant_id: str,
    document_id: str,
    layout_hash: str,
    corrections: List[Tuple[str, str]],
    auth_db_path: Optional[Path] = None,
) -> int:
    if not corrections:
        return 0
    ensure_ocr_corrections_table(auth_db_path)
    db_path = Path(auth_db_path or Config.AUTH_DB)
    now = _utc_now()
    con = sqlite3.connect(str(db_path))
    inserted = 0
    try:
        for field_name, corrected_value in corrections:
            con.execute(
                """
                INSERT INTO ocr_corrections(tenant_id, document_id, field_name, corrected_value, layout_hash, created_at)
                VALUES(?,?,?,?,?,?)
                """,
                (tenant_id, document_id, field_name, corrected_value, layout_hash, now),
            )
            inserted += 1
        con.commit()
    finally:
        con.close()
    return inserted


def load_layout_corrections(
    tenant_id: str,
    layout_hash: str,
    auth_db_path: Optional[Path] = None,
    limit: int = 30,
) -> Dict[str, str]:
    if not tenant_id or not layout_hash:
        return {}
    ensure_ocr_corrections_table(auth_db_path)
    db_path = Path(auth_db_path or Config.AUTH_DB)
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            """
            SELECT field_name, corrected_value, MAX(created_at) AS latest
            FROM ocr_corrections
            WHERE tenant_id=? AND layout_hash=?
            GROUP BY field_name
            ORDER BY latest DESC
            LIMIT ?
            """,
            (tenant_id, layout_hash, max(1, int(limit))),
        ).fetchall()
        return {str(r["field_name"]): str(r["corrected_value"]) for r in rows}
    finally:
        con.close()


def apply_layout_corrections(suggestions: Dict[str, Any], corrections: Dict[str, str]) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """
    Applies deterministic layout corrections to suggestion payload.
    Returns (updated_suggestions, provenance_by_field).
    """
    if not corrections:
        return suggestions, {}

    updated = dict(suggestions)
    provenance: Dict[str, str] = {}
    map_targets = {
        "doctype": "doctype_suggested",
        "kdnr": "kdnr_suggested",
        "document_date": "doc_date_suggested",
        "name": "name_suggested",
        "address": "addr_suggested",
        "plzort": "plzort_suggested",
    }
    for field_name, corrected_value in corrections.items():
        key = map_targets.get(field_name)
        if not key:
            continue
        updated[key] = corrected_value
        provenance[key] = "aus frueherer Korrektur"
    return updated, provenance


def process_upload(file_path: Path, tenant_id: str) -> UploadResult:
    """
    Validates, scans, and prepares a file for the system.
    """
    started = perf_counter()
    if not file_path.exists():
        return UploadResult(
            success=False,
            error_code=UploadErrorCode.FILE_NOT_FOUND,
            error_message=_ERROR_MESSAGES[UploadErrorCode.FILE_NOT_FOUND],
        )

    file_size = file_path.stat().st_size
    if file_size > MAX_FILE_SIZE:
        _safe_unlink(file_path)
        _write_dead_letter(file_path, tenant_id, UploadErrorCode.FILE_TOO_LARGE.value)
        return UploadResult(
            success=False,
            error_code=UploadErrorCode.FILE_TOO_LARGE,
            error_message=_ERROR_MESSAGES[UploadErrorCode.FILE_TOO_LARGE],
            details={"file_size": file_size, "max_size": MAX_FILE_SIZE},
        )

    suffix = file_path.suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        _safe_unlink(file_path)
        _write_dead_letter(file_path, tenant_id, UploadErrorCode.UNSUPPORTED_EXTENSION.value)
        return UploadResult(
            success=False,
            error_code=UploadErrorCode.UNSUPPORTED_EXTENSION,
            error_message=_ERROR_MESSAGES[UploadErrorCode.UNSUPPORTED_EXTENSION],
            details={"suffix": suffix, "allowed": list(ALLOWED_EXTENSIONS)},
        )

    clean, reason = _scan_malware(file_path)
    if not clean:
        _audit_scan_event(file_path, tenant_id, reason.value)
        _write_dead_letter(file_path, tenant_id, reason.value)
        _safe_unlink(file_path)
        return UploadResult(
            success=False,
            error_code=reason,
            error_message=_ERROR_MESSAGES.get(reason, "Sicherheits-Fehler."),
        )

    if reason == UploadErrorCode.CLAMAV_UNAVAILABLE:
        _audit_scan_event(file_path, tenant_id, UploadErrorCode.CLEAN_UNSCANNED.value)
        logger.warning(
            "ClamAV unavailable for %s. Continuing because CLAMAV_OPTIONAL=1 is enabled.",
            file_path.name,
        )
    else:
        _audit_scan_event(file_path, tenant_id, UploadErrorCode.CLEAN.value)

    try:
        file_hash = _hash_file_sha256(file_path)
    except Exception as exc:
        logger.error("Hashing failed for %s: %s", file_path.name, exc)
        _safe_unlink(file_path)
        return UploadResult(
            success=False,
            error_code=UploadErrorCode.PIPELINE_ERROR,
            error_message="Fehler beim Berechnen des Dateihash.",
        )

    elapsed = perf_counter() - started
    if elapsed > INGESTION_TARGET_SECONDS:
        logger.warning(
            "Upload pipeline slow path detected (file=%s, tenant=%s, elapsed=%.3fs, target=%.3fs)",
            file_path.name,
            tenant_id,
            elapsed,
            INGESTION_TARGET_SECONDS,
        )
    
    return UploadResult(
        success=True,
        file_hash=file_hash,
        details={"elapsed": elapsed},
    )
