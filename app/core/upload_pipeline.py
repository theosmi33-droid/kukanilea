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
from datetime import datetime, timezone
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


def _write_dead_letter(file_path: Path, tenant_id: str, reason: str) -> None:
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
                },
                ensure_ascii=True,
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception as exc:
        logger.warning("Could not write dead-letter marker for %s: %s", file_path.name, exc)


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


def _scan_malware(file_path: Path) -> Tuple[bool, str]:
    """
    Mandatory ClamAV gate.
    Returns: (is_clean, reason_code)
    reason_code: CLEAN | INFECTED | CLAMAV_UNAVAILABLE
    """
    try:
        import pyclamd

        cd = pyclamd.ClamdUnixSocket()
        if not cd.ping():
            if os.environ.get("CLAMAV_OPTIONAL") == "1":
                return True, "CLAMAV_UNAVAILABLE"
            return False, "CLAMAV_UNAVAILABLE"
        result = cd.scan_file(str(file_path))
        if result:
            logger.warning("Malware detected in %s", file_path.name)
            return False, "INFECTED"
        return True, "CLEAN"
    except Exception:
        if os.environ.get("CLAMAV_OPTIONAL") == "1":
            return True, "CLAMAV_UNAVAILABLE"
        return False, "CLAMAV_UNAVAILABLE"


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


def process_upload(file_path: Path, tenant_id: str) -> Tuple[bool, str]:
    """
    Validates, scans, and prepares a file for the system.
    """
    started = perf_counter()
    if not file_path.exists():
        return False, "Datei wurde nicht gefunden."

    if file_path.stat().st_size > MAX_FILE_SIZE:
        _safe_unlink(file_path)
        _write_dead_letter(file_path, tenant_id, "FILE_TOO_LARGE")
        return False, "Datei ist zu gross. Bitte reduzieren Sie die Dateigroesse."

    if file_path.suffix.lower() not in ALLOWED_EXTENSIONS:
        _safe_unlink(file_path)
        _write_dead_letter(file_path, tenant_id, "UNSUPPORTED_EXTENSION")
        return False, "Dateityp wird nicht unterstuetzt."

    clean, reason = _scan_malware(file_path)
    if not clean:
        if reason == "INFECTED":
            _audit_scan_event(file_path, tenant_id, "INFECTED")
            _write_dead_letter(file_path, tenant_id, "INFECTED")
            _safe_unlink(file_path)
            return False, "Sicherheitsrisiko erkannt. Datei wurde blockiert."
        if reason == "CLAMAV_UNAVAILABLE" and _clamav_optional_enabled():
            logger.warning(
                "ClamAV unavailable for %s. Continuing because CLAMAV_OPTIONAL=1 is enabled.",
                file_path.name,
            )
            _audit_scan_event(file_path, tenant_id, "CLAMAV_OPTIONAL_BYPASS")
        else:
            _audit_scan_event(file_path, tenant_id, "CLAMAV_UNAVAILABLE")
            _write_dead_letter(file_path, tenant_id, "CLAMAV_UNAVAILABLE")
            _safe_unlink(file_path)
            return False, "Virenscan derzeit nicht verfuegbar. Bitte starten Sie den ClamAV-Dienst und versuchen Sie es erneut."

    file_hash = _hash_file_sha256(file_path)
    _audit_scan_event(file_path, tenant_id, "CLEAN")

    elapsed = perf_counter() - started
    if elapsed > INGESTION_TARGET_SECONDS:
        logger.warning(
            "Upload pipeline slow path detected (file=%s, tenant=%s, elapsed=%.3fs, target=%.3fs)",
            file_path.name,
            tenant_id,
            elapsed,
            INGESTION_TARGET_SECONDS,
        )
    return True, file_hash
