from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from flask import current_app, has_app_context

from app.config import Config
from app.entity_links import list_links_for_entity
from app.event_id_map import entity_id_int
from app.lead_intake import lead_timeline, leads_get

SUPPORTED_ENTITY_TYPES = {"lead", "task", "knowledge_note"}


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _core_db_path() -> Path:
    if has_app_context():
        return Path(current_app.config["CORE_DB"])
    return Path(Config.CORE_DB)


def _open_db() -> sqlite3.Connection:
    con = sqlite3.connect(str(_core_db_path()), timeout=30)
    con.row_factory = sqlite3.Row
    return con


def _extract_request_id(payload: dict[str, Any]) -> str:
    rid = str(payload.get("request_id") or "").strip()
    if rid:
        return rid
    details = payload.get("details")
    if isinstance(details, dict):
        rid = str(details.get("request_id") or "").strip()
        if rid:
            return rid
    data = payload.get("data")
    if isinstance(data, dict):
        rid = str(data.get("request_id") or "").strip()
        if rid:
            return rid
    return ""


def _tenant_ok(payload: dict[str, Any], tenant_id: str) -> bool:
    tenant = str(payload.get("tenant_id") or "").strip()
    if not tenant:
        return False
    return tenant == str(tenant_id or "").strip()


def _event_rows_for_entity(
    tenant_id: str, entity_type: str, entity_id: str, limit: int = 250
) -> list[dict[str, Any]]:
    lim = max(1, min(int(limit), 500))
    e_type = str(entity_type or "").strip().lower()
    e_id = str(entity_id or "").strip()
    if not e_id:
        return []

    queries: list[tuple[str, tuple[Any, ...]]] = []
    queries.append(
        (
            """
            SELECT id, ts, event_type, entity_type, entity_id, payload_json
            FROM events
            WHERE entity_type=? AND entity_id=?
            ORDER BY id DESC
            LIMIT ?
            """,
            (e_type, entity_id_int(e_id), lim),
        )
    )

    key_map: dict[str, list[str]] = {
        "lead": ["lead_id"],
        "task": ["task_id"],
        "knowledge_note": ["chunk_id"],
    }
    for key in key_map.get(e_type, []):
        queries.append(
            (
                """
                SELECT id, ts, event_type, entity_type, entity_id, payload_json
                FROM events
                WHERE payload_json LIKE ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (f'%"{key}":"{e_id}"%', lim),
            )
        )

    seen: set[int] = set()
    out: list[dict[str, Any]] = []
    con = _open_db()
    try:
        for sql, params in queries:
            rows = con.execute(sql, params).fetchall()
            for row in rows:
                row_id = int(row["id"] or 0)
                if row_id <= 0 or row_id in seen:
                    continue
                seen.add(row_id)
                item = dict(row)
                try:
                    payload = json.loads(str(item.get("payload_json") or "{}"))
                except Exception:
                    payload = {}
                if not isinstance(payload, dict):
                    payload = {}
                if not _tenant_ok(payload, tenant_id):
                    continue
                item["payload"] = payload
                out.append(item)
    finally:
        con.close()

    out.sort(
        key=lambda x: (str(x.get("ts") or ""), int(x.get("id") or 0)), reverse=True
    )
    return out[:lim]


def _task_snapshot(tenant_id: str, task_id: str) -> dict[str, Any] | None:
    con = _open_db()
    try:
        row = con.execute(
            """
            SELECT id, tenant, status, title, details, priority, created_at, updated_at
            FROM tasks
            WHERE tenant=? AND id=?
            LIMIT 1
            """,
            (tenant_id, task_id),
        ).fetchone()
        return dict(row) if row else None
    except sqlite3.OperationalError:
        return None
    finally:
        con.close()


def _knowledge_note_snapshot(tenant_id: str, chunk_id: str) -> dict[str, Any] | None:
    con = _open_db()
    try:
        row = con.execute(
            """
            SELECT chunk_id, tenant_id, owner_user_id, source_type, source_ref, title,
                   substr(body, 1, 400) AS body_preview, tags, created_at, updated_at
            FROM knowledge_chunks
            WHERE tenant_id=? AND chunk_id=? AND source_type='manual'
            LIMIT 1
            """,
            (tenant_id, chunk_id),
        ).fetchone()
        return dict(row) if row else None
    except sqlite3.OperationalError:
        return None
    finally:
        con.close()


def _linked_attachments(
    tenant_id: str, entity_type: str, entity_id: str
) -> list[dict[str, Any]]:
    rows = list_links_for_entity(
        tenant_id=tenant_id,
        entity_type=entity_type,
        entity_id=entity_id,
        limit=200,
    )
    out: list[dict[str, Any]] = []
    for row in rows:
        link_type = str(row.get("link_type") or "")
        if link_type not in {"attachment", "references", "related"}:
            continue
        out.append(
            {
                "link_id": str(row.get("id") or ""),
                "link_type": link_type,
                "entity_type": str(row.get("other_type") or ""),
                "entity_id": str(row.get("other_id") or ""),
                "created_at": str(row.get("created_at") or ""),
            }
        )
    return out


def build_evidence_pack(
    *,
    tenant_id: str,
    entity_type: str,
    entity_id: str,
    limit: int = 250,
) -> dict[str, Any] | None:
    t = str(tenant_id or "").strip()
    e_type = str(entity_type or "").strip().lower()
    e_id = str(entity_id or "").strip()
    if e_type not in SUPPORTED_ENTITY_TYPES:
        raise ValueError("validation_error")
    if not e_id:
        raise ValueError("validation_error")

    snapshot: dict[str, Any] | None
    timeline: dict[str, Any]
    if e_type == "lead":
        snapshot = leads_get(t, e_id)
        if not snapshot:
            return None
        timeline = lead_timeline(t, e_id, limit=limit)
        timeline_events = []
        for item in timeline.get("events") or []:
            payload = item.get("payload")
            if not isinstance(payload, dict):
                continue
            if not _tenant_ok(payload, t):
                continue
            timeline_events.append(item)
        timeline["events"] = timeline_events
    elif e_type == "task":
        snapshot = _task_snapshot(t, e_id)
        if not snapshot:
            return None
        timeline = {"events": _event_rows_for_entity(t, e_type, e_id, limit=limit)}
    else:  # knowledge_note
        snapshot = _knowledge_note_snapshot(t, e_id)
        if not snapshot:
            return None
        timeline = {"events": _event_rows_for_entity(t, e_type, e_id, limit=limit)}

    attachments = _linked_attachments(t, e_type, e_id)
    request_ids: set[str] = set()
    for row in timeline.get("events") or []:
        payload = row.get("payload")
        if isinstance(payload, dict):
            rid = _extract_request_id(payload)
            if rid:
                request_ids.add(rid)

    return {
        "generated_at": _now_iso(),
        "tenant_id": t,
        "entity_type": e_type,
        "entity_id": e_id,
        "entity": snapshot,
        "timeline": timeline,
        "attachments": attachments,
        "request_ids": sorted(request_ids),
    }
