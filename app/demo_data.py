from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def _table_columns(con: sqlite3.Connection, table: str) -> set[str]:
    rows = con.execute(f"PRAGMA table_info({table})").fetchall()
    return {str(r["name"]) for r in rows}


def _table_exists(con: sqlite3.Connection, table: str) -> bool:
    row = con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=? LIMIT 1", (table,)
    ).fetchone()
    return bool(row)


def _insert(con: sqlite3.Connection, table: str, payload: dict[str, Any]) -> int:
    if not _table_exists(con, table):
        return 0
    cols = _table_columns(con, table)
    values = {k: v for k, v in payload.items() if k in cols}
    if not values:
        return 0
    keys = list(values.keys())
    placeholders = ",".join("?" for _ in keys)
    sql = f"INSERT OR IGNORE INTO {table} ({','.join(keys)}) VALUES ({placeholders})"
    cur = con.execute(sql, tuple(values[k] for k in keys))
    return 1 if cur.rowcount and cur.rowcount > 0 else 0


def _new_text_id(prefix: str, tenant_id: str, idx: int) -> str:
    seed = f"{prefix}|{tenant_id}|{idx}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]


def generate_demo_data(*, db_path: Path, tenant_id: str) -> dict[str, int]:
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    now = _now_iso()
    created = {
        "customers": 0,
        "leads": 0,
        "projects": 0,
        "tasks": 0,
        "knowledge_notes": 0,
        "sample_emails": 0,
    }
    try:
        customers = ["Demo GmbH", "Test AG", "Baupartner KG"]
        customer_ids: list[str] = []
        for i, name in enumerate(customers, start=1):
            cid = _new_text_id("customer", tenant_id, i)
            customer_ids.append(cid)
            created["customers"] += _insert(
                con,
                "customers",
                {
                    "id": cid,
                    "tenant_id": tenant_id,
                    "name": name,
                    "vat_id": f"DEMO-{i:04d}",
                    "notes": "Demo record",
                    "created_at": now,
                    "updated_at": now,
                },
            )

        statuses = ["new", "contacted", "qualified", "won", "lost"]
        for i in range(10):
            lid = _new_text_id("lead", tenant_id, i)
            created["leads"] += _insert(
                con,
                "leads",
                {
                    "id": lid,
                    "tenant_id": tenant_id,
                    "status": statuses[i % len(statuses)],
                    "source": "manual",
                    "customer_id": customer_ids[i % len(customer_ids)]
                    if customer_ids
                    else None,
                    "contact_name": f"Kontakt {i + 1}",
                    "contact_email": f"demo{i + 1}@example.com",
                    "subject": f"Demo Lead {i + 1}",
                    "message": "Demo lead message",
                    "created_at": now,
                    "updated_at": now,
                },
            )

        project_ids: list[int] = []
        if _table_exists(con, "time_projects"):
            for i in range(3):
                cur = con.execute(
                    """
                    INSERT INTO time_projects(
                      tenant_id, name, description, status, budget_hours, budget_cost, created_by, created_at, updated_at
                    ) VALUES (?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        tenant_id,
                        f"Projekt {i + 1}",
                        "Demo Projekt",
                        "ACTIVE",
                        40,
                        2000.0,
                        "demo",
                        now,
                        now,
                    ),
                )
                if cur.rowcount and cur.rowcount > 0:
                    created["projects"] += 1
                    project_ids.append(int(cur.lastrowid))

        task_states = ["OPEN", "IN_PROGRESS", "RESOLVED"]
        for i in range(15):
            created["tasks"] += _insert(
                con,
                "tasks",
                {
                    "ts": now,
                    "tenant": tenant_id,
                    "severity": "INFO",
                    "task_type": "GENERAL",
                    "status": task_states[i % len(task_states)],
                    "title": f"Demo Task {i + 1}",
                    "details": "Automatisch erzeugt",
                    "meta_json": json.dumps(
                        {
                            "project_id": project_ids[i % len(project_ids)]
                            if project_ids
                            else None
                        }
                    ),
                    "created_by": "demo",
                },
            )

        for i in range(5):
            body = f"Dies ist eine Demo-Notiz {i + 1} fuer Tenant {tenant_id}."
            created["knowledge_notes"] += _insert(
                con,
                "knowledge_chunks",
                {
                    "chunk_id": _new_text_id("note", tenant_id, i),
                    "tenant_id": tenant_id,
                    "owner_user_id": "demo",
                    "source_type": "manual",
                    "source_ref": f"demo-note-{i + 1}",
                    "title": f"Demo Notiz {i + 1}",
                    "body": body,
                    "tags": "demo",
                    "content_hash": hashlib.sha256(body.encode("utf-8")).hexdigest(),
                    "is_redacted": 1,
                    "created_at": now,
                    "updated_at": now,
                },
            )

        for i in range(3):
            created["sample_emails"] += _insert(
                con,
                "mail_messages",
                {
                    "id": _new_text_id("mail", tenant_id, i),
                    "tenant_id": tenant_id,
                    "account_id": "demo-account",
                    "uid": f"demo-{i + 1}",
                    "message_id": f"<demo-{i + 1}@example.com>",
                    "from_redacted": "d***@example.com",
                    "to_redacted": "t***@example.com",
                    "subject_redacted": f"Demo Mail {i + 1}",
                    "received_at": now,
                    "body_text_redacted": "Dies ist eine redigierte Demo-Mail.",
                    "has_attachments": 0,
                    "created_at": now,
                },
            )

        con.commit()
        return created
    finally:
        con.close()
