from __future__ import annotations

import csv
import io
import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# We need to import core functionality, but since we are decoupling,
# we expect these to be passed or available via app.core
try:
    from app import core as legacy_core
    from app.core.logic import _effective_tenant, TENANT_DEFAULT
    _DB_LOCK = getattr(legacy_core, "_DB_LOCK", threading.Lock())
    # Ensure these are available on legacy_core even if imported from logic
    if not hasattr(legacy_core, "_db"):
        from app.core.db_utils import _db
        legacy_core._db = _db # type: ignore
    if not hasattr(legacy_core, "normalize_component"):
        from app.core.logic import normalize_component
        legacy_core.normalize_component = normalize_component # type: ignore
    if not hasattr(legacy_core, "audit_log"):
        from app.core.logic import audit_log
        legacy_core.audit_log = audit_log # type: ignore
except ImportError:
    class MockCore:
        def _db(self):
            path = os.environ.get("DB_FILENAME", "core.sqlite3")
            conn = sqlite3.connect(path)
            conn.row_factory = sqlite3.Row
            return conn
        def normalize_component(self, x): return str(x or "").strip()
        def audit_log(self, **kwargs): pass
        def _run_write_txn(self, fn):
            with self._db() as con:
                res = fn(con)
                con.commit()
                return res
        def _run_read_txn(self, fn):
            with self._db() as con:
                return fn(con)
    legacy_core = MockCore() # type: ignore
    _effective_tenant = lambda x: x or "default"
    TENANT_DEFAULT = "default"
    _DB_LOCK = threading.Lock()

# Re-implementing small helpers or importing from core
def _time_tenant(tenant_id: str) -> str:
    return _effective_tenant(tenant_id) or _effective_tenant(TENANT_DEFAULT) or "default"

def _parse_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)

def _duration_seconds(start_at: str, end_at: str) -> int:
    return max(0, int((_parse_iso(end_at) - _parse_iso(start_at)).total_seconds()))

def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def time_project_create(
    *,
    tenant_id: str,
    name: str,
    description: str = "",
    created_by: str = "",
) -> Dict[str, Any]:
    tenant_id = _time_tenant(tenant_id)
    name = legacy_core.normalize_component(name)
    description = (description or "").strip()
    created_by = legacy_core.normalize_component(created_by).lower()
    if not name:
        raise ValueError("project_name_required")

    now = _now_iso()
    project_id = 0
    with _DB_LOCK:
        con = legacy_core._db()
        try:
            cur = con.execute(
                """
                INSERT INTO time_projects(tenant_id, name, description, status, created_by, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?)
                """,
                (tenant_id, name, description, "ACTIVE", created_by, now, now),
            )
            con.commit()
            project_id = int(cur.lastrowid or 0)
        finally:
            con.close()
    legacy_core.audit_log(
        user=created_by or "system",
        role="SYSTEM",
        action="TIME_PROJECT_CREATE",
        target=str(project_id),
        meta={"name": name},
        tenant_id=tenant_id,
    )
    return {
        "id": project_id,
        "tenant_id": tenant_id,
        "name": name,
        "description": description,
        "status": "ACTIVE",
        "created_by": created_by,
        "created_at": now,
        "updated_at": now,
    }

def time_project_list(
    *, tenant_id: str, status: str = "ACTIVE"
) -> List[Dict[str, Any]]:
    tenant_id = _time_tenant(tenant_id)
    status = legacy_core.normalize_component(status).upper() or "ACTIVE"
    with _DB_LOCK:
        con = legacy_core._db()
        try:
            rows = con.execute(
                """
                SELECT * FROM time_projects
                WHERE tenant_id=? AND status=?
                ORDER BY name
                """,
                (tenant_id, status),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            con.close()

def _time_project_lookup(
    con: sqlite3.Connection, tenant_id: str, project_id: Optional[int]
) -> Optional[dict]:
    if project_id is None:
        return None
    row = con.execute(
        "SELECT * FROM time_projects WHERE id=? AND tenant_id=?",
        (int(project_id), tenant_id),
    ).fetchone()
    return dict(row) if row else None

def time_entry_start(
    *,
    tenant_id: str,
    user: str,
    project_id: Optional[int] = None,
    note: str = "",
    started_at: Optional[str] = None,
) -> Dict[str, Any]:
    tenant_id = _time_tenant(tenant_id)
    user = legacy_core.normalize_component(user).lower()
    note = (note or "").strip()
    if not user:
        raise ValueError("user_required")

    now = started_at or _now_iso()
    entry_id = 0
    with _DB_LOCK:
        con = legacy_core._db()
        try:
            if project_id is not None and not _time_project_lookup(
                con, tenant_id, project_id
            ):
                raise ValueError("project_not_found")
            row = con.execute(
                "SELECT id FROM time_entries WHERE tenant_id=? AND user=? AND end_at IS NULL",
                (tenant_id, user),
            ).fetchone()
            if row:
                raise ValueError("running_timer_exists")
            cur = con.execute(
                """
                INSERT INTO time_entries(
                    tenant_id, project_id, user, start_at, end_at, duration_seconds, note,
                    approval_status, created_at, updated_at
                )
                VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    tenant_id,
                    project_id,
                    user,
                    now,
                    None,
                    None,
                    note,
                    "PENDING",
                    now,
                    now,
                ),
            )
            con.commit()
            entry_id = int(cur.lastrowid or 0)
        finally:
            con.close()
    legacy_core.audit_log(
        user=user,
        role="OPERATOR",
        action="TIME_ENTRY_START",
        target=str(entry_id),
        meta={"project_id": project_id or ""},
        tenant_id=tenant_id,
    )
    return time_entry_get(tenant_id=tenant_id, entry_id=entry_id) or {}

def time_entry_get(*, tenant_id: str, entry_id: int) -> Optional[Dict[str, Any]]:
    tenant_id = _time_tenant(tenant_id)
    with _DB_LOCK:
        con = legacy_core._db()
        try:
            row = con.execute(
                """
                SELECT te.*, tp.name AS project_name
                FROM time_entries te
                LEFT JOIN time_projects tp ON tp.id = te.project_id
                WHERE te.tenant_id=? AND te.id=?
                """,
                (tenant_id, int(entry_id)),
            ).fetchone()
            if not row:
                return None
            entry = dict(row)
            if entry.get("end_at"):
                entry["duration_seconds"] = _duration_seconds(
                    entry["start_at"], entry["end_at"]
                )
            else:
                entry["duration_seconds"] = _duration_seconds(
                    entry["start_at"], _now_iso()
                )
            return entry
        finally:
            con.close()

def time_entry_stop(
    *,
    tenant_id: str,
    user: str,
    entry_id: Optional[int] = None,
    ended_at: Optional[str] = None,
) -> Dict[str, Any]:
    tenant_id = _time_tenant(tenant_id)
    user = legacy_core.normalize_component(user).lower()
    if not user:
        raise ValueError("user_required")
    end_ts = ended_at or _now_iso()

    with _DB_LOCK:
        con = legacy_core._db()
        try:
            if entry_id is None:
                row = con.execute(
                    """
                    SELECT id, start_at FROM time_entries
                    WHERE tenant_id=? AND user=? AND end_at IS NULL
                    """,
                    (tenant_id, user),
                ).fetchone()
            else:
                row = con.execute(
                    """
                    SELECT id, start_at FROM time_entries
                    WHERE tenant_id=? AND user=? AND id=?
                    """,
                    (tenant_id, user, int(entry_id)),
                ).fetchone()
            if not row:
                raise ValueError("no_running_timer")
            start_at = str(row["start_at"])
            if _parse_iso(end_ts) < _parse_iso(start_at):
                raise ValueError("invalid_time_range")
            duration = _duration_seconds(start_at, end_ts)
            con.execute(
                """
                UPDATE time_entries
                SET end_at=?, duration_seconds=?, updated_at=?
                WHERE id=? AND tenant_id=?
                """,
                (end_ts, duration, _now_iso(), int(row["id"]), tenant_id),
            )
            con.commit()
            stopped_id = int(row["id"])
        finally:
            con.close()
    legacy_core.audit_log(
        user=user,
        role="OPERATOR",
        action="TIME_ENTRY_STOP",
        target=str(stopped_id),
        meta={"duration_seconds": duration},
        tenant_id=tenant_id,
    )
    return time_entry_get(tenant_id=tenant_id, entry_id=stopped_id) or {}

def time_entry_update(
    *,
    tenant_id: str,
    entry_id: int,
    project_id: Optional[int] = None,
    start_at: Optional[str] = None,
    end_at: Optional[str] = None,
    note: Optional[str] = None,
    user: str = "",
) -> Dict[str, Any]:
    tenant_id = _time_tenant(tenant_id)
    user = legacy_core.normalize_component(user).lower()

    with _DB_LOCK:
        con = legacy_core._db()
        try:
            row = con.execute(
                "SELECT * FROM time_entries WHERE id=? AND tenant_id=?",
                (int(entry_id), tenant_id),
            ).fetchone()
            if not row:
                raise ValueError("entry_not_found")
            if project_id is not None and not _time_project_lookup(
                con, tenant_id, project_id
            ):
                raise ValueError("project_not_found")
            start_val = start_at or row["start_at"]
            end_val = end_at if end_at is not None else row["end_at"]
            duration_val = None
            if end_val:
                if _parse_iso(end_val) < _parse_iso(start_val):
                    raise ValueError("invalid_time_range")
                duration_val = _duration_seconds(start_val, end_val)
            con.execute(
                """
                UPDATE time_entries
                SET project_id=?, start_at=?, end_at=?, duration_seconds=?, note=?, updated_at=?
                WHERE id=? AND tenant_id=?
                """,
                (
                    project_id if project_id is not None else row["project_id"],
                    start_val,
                    end_val,
                    duration_val,
                    note if note is not None else row["note"],
                    _now_iso(),
                    int(entry_id),
                    tenant_id,
                ),
            )
            con.commit()
        finally:
            con.close()
    legacy_core.audit_log(
        user=user or "system",
        role="OPERATOR",
        action="TIME_ENTRY_EDIT",
        target=str(entry_id),
        meta={"project_id": project_id or "", "note_changed": note is not None},
        tenant_id=tenant_id,
    )
    return time_entry_get(tenant_id=tenant_id, entry_id=int(entry_id)) or {}

def time_entry_approve(
    *, tenant_id: str, entry_id: int, approved_by: str
) -> Dict[str, Any]:
    tenant_id = _time_tenant(tenant_id)
    approved_by = legacy_core.normalize_component(approved_by).lower()
    if not approved_by:
        raise ValueError("approved_by_required")
    now = _now_iso()
    with _DB_LOCK:
        con = legacy_core._db()
        try:
            row = con.execute(
                "SELECT id FROM time_entries WHERE id=? AND tenant_id=?",
                (int(entry_id), tenant_id),
            ).fetchone()
            if not row:
                raise ValueError("entry_not_found")
            con.execute(
                """
                UPDATE time_entries
                SET approval_status=?, approved_by=?, approved_at=?, updated_at=?
                WHERE id=? AND tenant_id=?
                """,
                ("APPROVED", approved_by, now, now, int(entry_id), tenant_id),
            )
            con.commit()
        finally:
            con.close()
    legacy_core.audit_log(
        user=approved_by,
        role="ADMIN",
        action="TIME_ENTRY_APPROVE",
        target=str(entry_id),
        meta={},
        tenant_id=tenant_id,
    )
    return time_entry_get(tenant_id=tenant_id, entry_id=int(entry_id)) or {}

def time_entries_list(
    *,
    tenant_id: str,
    user: Optional[str] = None,
    start_at: Optional[str] = None,
    end_at: Optional[str] = None,
    limit: int = 500,
) -> List[Dict[str, Any]]:
    tenant_id = _time_tenant(tenant_id)
    user = legacy_core.normalize_component(user or "").lower()
    limit = max(1, min(int(limit), 2000))

    clauses = ["te.tenant_id=?"]
    params: List[Any] = [tenant_id]
    if user:
        clauses.append("te.user=?")
        params.append(user)
    if start_at:
        clauses.append("te.start_at>=?")
        params.append(start_at)
    if end_at:
        clauses.append("te.start_at<=?")
        params.append(end_at)

    where_sql = " AND ".join(clauses)
    with _DB_LOCK:
        con = legacy_core._db()
        try:
            rows = con.execute(
                f"""
                SELECT te.*, tp.name AS project_name
                FROM time_entries te
                LEFT JOIN time_projects tp ON tp.id = te.project_id
                WHERE {where_sql}
                ORDER BY te.start_at DESC, te.id DESC
                LIMIT ?
                """,
                (*params, limit),
            ).fetchall()
            entries = [dict(r) for r in rows]
            now = _now_iso()
            for entry in entries:
                if entry.get("end_at"):
                    entry["duration_seconds"] = _duration_seconds(
                        entry["start_at"], entry["end_at"]
                    )
                else:
                    entry["duration_seconds"] = _duration_seconds(
                        entry["start_at"], now
                    )
            return entries
        finally:
            con.close()

def time_entries_export_csv(
    *,
    tenant_id: str,
    user: Optional[str] = None,
    start_at: Optional[str] = None,
    end_at: Optional[str] = None,
    limit: int = 2000,
) -> str:
    entries = time_entries_list(
        tenant_id=tenant_id,
        user=user,
        start_at=start_at,
        end_at=end_at,
        limit=limit,
    )
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "entry_id",
            "project_id",
            "project_name",
            "user",
            "start_at",
            "end_at",
            "duration_seconds",
            "duration_hours",
            "note",
            "approval_status",
            "approved_by",
            "approved_at",
        ]
    )
    for entry in entries[:2000]: # MAX_CSV_ROWS
        duration_seconds = int(entry.get("duration_seconds") or 0)
        writer.writerow(
            [
                entry.get("id"),
                entry.get("project_id"),
                entry.get("project_name") or "",
                entry.get("user"),
                entry.get("start_at"),
                entry.get("end_at") or "",
                duration_seconds,
                round(duration_seconds / 3600.0, 2),
                entry.get("note") or "",
                entry.get("approval_status") or "",
                entry.get("approved_by") or "",
                entry.get("approved_at") or "",
            ]
        )
    return output.getvalue()
