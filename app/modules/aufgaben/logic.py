from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime
from typing import Any

from app.core.logic import DB_PATH

OPEN_STATUSES = {"OPEN", "IN_PROGRESS", "BLOCKED"}
PRIORITIES = {"LOW", "MEDIUM", "HIGH", "URGENT"}


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _db() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def ensure_schema() -> None:
    con = _db()
    try:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS aufgaben_tasks(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              tenant TEXT NOT NULL,
              title TEXT NOT NULL,
              details TEXT,
              status TEXT NOT NULL DEFAULT 'OPEN',
              due_date TEXT,
              priority TEXT NOT NULL DEFAULT 'MEDIUM',
              assigned_to TEXT,
              source_type TEXT,
              source_ref TEXT,
              created_by TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            """
        )
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_aufgaben_tenant_status ON aufgaben_tasks(tenant, status, due_date);"
        )
        con.commit()
    finally:
        con.close()


def _norm_priority(value: str | None) -> str:
    normalized = str(value or "MEDIUM").strip().upper()
    return normalized if normalized in PRIORITIES else "MEDIUM"


def _norm_status(value: str | None) -> str:
    normalized = str(value or "OPEN").strip().upper()
    return normalized if normalized else "OPEN"


def _task_row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row else None


def create_task(
    *,
    tenant: str,
    title: str,
    details: str = "",
    due_date: str | None = None,
    priority: str = "MEDIUM",
    assigned_to: str | None = None,
    source_type: str | None = None,
    source_ref: str | None = None,
    created_by: str = "system",
) -> dict[str, Any]:
    ensure_schema()
    now = _now_iso()
    con = _db()
    try:
        cur = con.execute(
            """
            INSERT INTO aufgaben_tasks(
                tenant, title, details, status, due_date, priority,
                assigned_to, source_type, source_ref, created_by,
                created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                str(tenant),
                str(title).strip() or "Neue Aufgabe",
                str(details or "").strip(),
                "OPEN",
                str(due_date).strip() if due_date else None,
                _norm_priority(priority),
                str(assigned_to).strip() if assigned_to else None,
                str(source_type).strip() if source_type else None,
                str(source_ref).strip() if source_ref else None,
                str(created_by or "system"),
                now,
                now,
            ),
        )
        task_id = int(cur.lastrowid or 0)
        con.commit()
        row = con.execute("SELECT * FROM aufgaben_tasks WHERE id=?", (task_id,)).fetchone()
        return _task_row_to_dict(row) or {}
    finally:
        con.close()


def list_tasks(*, tenant: str, status: str | None = None) -> list[dict[str, Any]]:
    ensure_schema()
    con = _db()
    try:
        if status:
            rows = con.execute(
                "SELECT * FROM aufgaben_tasks WHERE tenant=? AND status=? ORDER BY id DESC",
                (str(tenant), _norm_status(status)),
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT * FROM aufgaben_tasks WHERE tenant=? ORDER BY id DESC",
                (str(tenant),),
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def get_task(*, tenant: str, task_id: int) -> dict[str, Any] | None:
    ensure_schema()
    con = _db()
    try:
        row = con.execute(
            "SELECT * FROM aufgaben_tasks WHERE tenant=? AND id=?",
            (str(tenant), int(task_id)),
        ).fetchone()
        return _task_row_to_dict(row)
    finally:
        con.close()


def update_task(*, tenant: str, task_id: int, payload: dict[str, Any]) -> dict[str, Any] | None:
    ensure_schema()
    existing = get_task(tenant=tenant, task_id=task_id)
    if not existing:
        return None

    title = str(payload.get("title", existing["title"]))
    details = str(payload.get("details", existing.get("details") or ""))
    status = _norm_status(payload.get("status", existing["status"]))
    due_date = payload.get("due_date", existing.get("due_date"))
    priority = _norm_priority(payload.get("priority", existing["priority"]))
    assigned_to = payload.get("assigned_to", existing.get("assigned_to"))
    source_type = payload.get("source_type", existing.get("source_type"))
    source_ref = payload.get("source_ref", existing.get("source_ref"))

    con = _db()
    try:
        con.execute(
            """
            UPDATE aufgaben_tasks
            SET title=?, details=?, status=?, due_date=?, priority=?, assigned_to=?,
                source_type=?, source_ref=?, updated_at=?
            WHERE tenant=? AND id=?
            """,
            (
                title.strip() or existing["title"],
                details.strip(),
                status,
                str(due_date).strip() if due_date else None,
                priority,
                str(assigned_to).strip() if assigned_to else None,
                str(source_type).strip() if source_type else None,
                str(source_ref).strip() if source_ref else None,
                _now_iso(),
                str(tenant),
                int(task_id),
            ),
        )
        con.commit()
    finally:
        con.close()

    return get_task(tenant=tenant, task_id=task_id)


def delete_task(*, tenant: str, task_id: int) -> bool:
    ensure_schema()
    con = _db()
    try:
        cur = con.execute(
            "DELETE FROM aufgaben_tasks WHERE tenant=? AND id=?",
            (str(tenant), int(task_id)),
        )
        con.commit()
        return int(cur.rowcount or 0) > 0
    finally:
        con.close()


def summary(*, tenant: str, today_value: date | None = None) -> dict[str, int]:
    ensure_schema()
    tasks = list_tasks(tenant=tenant)
    today = today_value or datetime.now(UTC).date()
    open_count = 0
    overdue = 0
    due_today = 0

    for task in tasks:
        status = str(task.get("status") or "").upper()
        if status not in OPEN_STATUSES:
            continue
        open_count += 1
        raw_due = str(task.get("due_date") or "").strip()
        if not raw_due:
            continue
        due_date = _parse_due_date(raw_due)
        if due_date is None:
            continue
        if due_date < today:
            overdue += 1
        if due_date == today:
            due_today += 1

    return {"open": open_count, "overdue": overdue, "today": due_today}


def _parse_due_date(raw_due: str) -> date | None:
    try:
        if "T" in raw_due:
            parsed = datetime.fromisoformat(raw_due.replace("Z", "+00:00"))
            return parsed.date()
        return date.fromisoformat(raw_due[:10])
    except ValueError:
        return None
