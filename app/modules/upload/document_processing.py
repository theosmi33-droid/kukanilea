from __future__ import annotations

import json
import logging
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from app.config import Config
from app.logging.structured_logger import log_event

logger = logging.getLogger("kukanilea.document_processing")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _connect(db_path: Path | None = None) -> sqlite3.Connection:
    con = sqlite3.connect(str(db_path or Config.AUTH_DB))
    con.row_factory = sqlite3.Row
    return con


def ensure_document_processing_tables(db_path: Path | None = None) -> None:
    con = _connect(db_path)
    try:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS document_uploads(
              id TEXT PRIMARY KEY,
              tenant_id TEXT NOT NULL,
              filename TEXT NOT NULL,
              file_type TEXT NOT NULL,
              file_hash TEXT NOT NULL,
              size_bytes INTEGER NOT NULL,
              stored_path TEXT NOT NULL,
              summary_stub TEXT NOT NULL,
              deadline_stub TEXT NOT NULL,
              metadata_json TEXT NOT NULL,
              created_at TEXT NOT NULL,
              processed_at TEXT
            )
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS document_processing_queue(
              id TEXT PRIMARY KEY,
              tenant_id TEXT NOT NULL,
              upload_id TEXT NOT NULL,
              status TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              error_message TEXT,
              FOREIGN KEY(upload_id) REFERENCES document_uploads(id) ON DELETE CASCADE
            )
            """
        )
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_document_uploads_tenant_created ON document_uploads(tenant_id, created_at DESC)"
        )
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_document_queue_tenant_status ON document_processing_queue(tenant_id, status, created_at DESC)"
        )
        con.commit()
    finally:
        con.close()


def _summary_stub(filename: str, file_type: str, size_bytes: int) -> str:
    return (
        f"Stub: Dokument '{filename}' ({file_type}, {size_bytes} Bytes) "
        "wurde aufgenommen. Zusammenfassung folgt nach fachlicher Extraktion."
    )


def _deadline_detection_stub() -> dict[str, Any]:
    return {
        "status": "not_implemented",
        "candidate_deadlines": [],
        "note": "Deadline-Erkennung ist als Stub aktiv und liefert noch keine verbindlichen Fristen.",
    }


def _resolve_virus_scan_hook() -> Callable[[Path, str], tuple[bool, str]] | None:
    hook = str(os.environ.get("KUKANILEA_VIRUS_SCAN_HOOK", "")).strip()
    if not hook or ":" not in hook:
        return None
    module_name, fn_name = hook.split(":", 1)
    try:
        module = __import__(module_name, fromlist=[fn_name])
        fn = getattr(module, fn_name, None)
        if callable(fn):
            return fn
    except Exception as exc:
        logger.warning("Virus scan hook could not be loaded (%s): %s", hook, exc)
    return None


def run_virus_scan_hook(file_path: Path, tenant_id: str) -> tuple[bool, str]:
    fn = _resolve_virus_scan_hook()
    if fn is None:
        return True, "hook_not_configured"
    try:
        clean, reason = fn(file_path, tenant_id)
        return bool(clean), str(reason or "hook_executed")
    except Exception as exc:
        logger.warning("Virus scan hook failed for %s: %s", file_path.name, exc)
        return False, "hook_failed"


def register_document_upload(
    *,
    file_path: Path,
    tenant_id: str,
    file_hash: str,
    db_path: Path | None = None,
) -> dict[str, Any]:
    ensure_document_processing_tables(db_path)

    now = _utc_now()
    file_type = file_path.suffix.lower().lstrip(".") or "unknown"
    size_bytes = file_path.stat().st_size if file_path.exists() else 0
    upload_id = str(uuid.uuid4())
    queue_id = str(uuid.uuid4())

    metadata = {
        "filename": file_path.name,
        "type": file_type,
        "hash": file_hash,
        "tenant": tenant_id,
        "size_bytes": size_bytes,
    }
    summary = _summary_stub(file_path.name, file_type, size_bytes)
    deadline = _deadline_detection_stub()

    con = _connect(db_path)
    try:
        con.execute(
            """
            INSERT INTO document_uploads(
              id, tenant_id, filename, file_type, file_hash, size_bytes, stored_path,
              summary_stub, deadline_stub, metadata_json, created_at, processed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                upload_id,
                tenant_id,
                file_path.name,
                file_type,
                file_hash,
                size_bytes,
                str(file_path),
                summary,
                json.dumps(deadline, ensure_ascii=True),
                json.dumps(metadata, ensure_ascii=True),
                now,
                now,
            ),
        )
        queue_payload = {
            "upload_id": upload_id,
            "event_types": ["document.uploaded", "document.processed"],
            "metadata": metadata,
            "summary_stub": summary,
            "deadline_detection": deadline,
        }
        con.execute(
            """
            INSERT INTO document_processing_queue(id, tenant_id, upload_id, status, payload_json, created_at, updated_at)
            VALUES (?, ?, ?, 'processed', ?, ?, ?)
            """,
            (queue_id, tenant_id, upload_id, json.dumps(queue_payload, ensure_ascii=True), now, now),
        )
        con.commit()
    finally:
        con.close()

    uploaded_event = {
        "upload_id": upload_id,
        "tenant": tenant_id,
        "metadata": metadata,
        "created_at": now,
    }
    processed_event = {
        "upload_id": upload_id,
        "tenant": tenant_id,
        "summary_stub": summary,
        "deadline_detection": deadline,
        "processed_at": now,
    }
    log_event("document.uploaded", uploaded_event)
    log_event("document.processed", processed_event)

    return {
        "upload_id": upload_id,
        "queue_id": queue_id,
        "metadata": metadata,
        "summary_stub": summary,
        "deadline_detection": deadline,
        "created_at": now,
        "processed_at": now,
    }


def list_recent_uploads(tenant_id: str, limit: int = 10, db_path: Path | None = None) -> list[dict[str, Any]]:
    ensure_document_processing_tables(db_path)
    con = _connect(db_path)
    try:
        rows = con.execute(
            """
            SELECT id, filename, file_type, file_hash, size_bytes, created_at, processed_at, summary_stub, deadline_stub
            FROM document_uploads
            WHERE tenant_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (tenant_id, max(1, int(limit))),
        ).fetchall()
        return [
            {
                "id": str(row["id"]),
                "filename": str(row["filename"]),
                "type": str(row["file_type"]),
                "hash": str(row["file_hash"]),
                "size_bytes": int(row["size_bytes"]),
                "created_at": str(row["created_at"]),
                "processed_at": str(row["processed_at"] or ""),
                "summary_stub": str(row["summary_stub"]),
                "deadline_detection": json.loads(str(row["deadline_stub"] or "{}")),
            }
            for row in rows
        ]
    finally:
        con.close()


def list_processing_queue(tenant_id: str, limit: int = 20, db_path: Path | None = None) -> list[dict[str, Any]]:
    ensure_document_processing_tables(db_path)
    con = _connect(db_path)
    try:
        rows = con.execute(
            """
            SELECT id, upload_id, status, payload_json, created_at, updated_at, error_message
            FROM document_processing_queue
            WHERE tenant_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (tenant_id, max(1, int(limit))),
        ).fetchall()
        return [
            {
                "id": str(row["id"]),
                "upload_id": str(row["upload_id"]),
                "status": str(row["status"]),
                "payload": json.loads(str(row["payload_json"] or "{}")),
                "created_at": str(row["created_at"]),
                "updated_at": str(row["updated_at"]),
                "error_message": str(row["error_message"] or ""),
            }
            for row in rows
        ]
    finally:
        con.close()
