#!/usr/bin/env python3
from __future__ import annotations

import os
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path



def _ts(offset_days: int = 0) -> str:
    return (datetime.utcnow() + timedelta(days=offset_days)).isoformat()


def _data_root() -> Path:
    return Path(os.environ.get("KUKANILEA_USER_DATA_ROOT", Path.cwd() / "instance"))


def _seed_auth(auth_db_path: Path, tenant_id: str) -> None:
    auth_db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(auth_db_path) as con:
        con.execute("CREATE TABLE IF NOT EXISTS users(username TEXT PRIMARY KEY, password_hash TEXT NOT NULL, needs_reset INTEGER DEFAULT 0, failed_attempts INTEGER DEFAULT 0, created_at TEXT NOT NULL)")
        con.execute("CREATE TABLE IF NOT EXISTS tenants(tenant_id TEXT PRIMARY KEY, display_name TEXT NOT NULL, core_db_path TEXT, created_at TEXT NOT NULL)")
        con.execute("CREATE TABLE IF NOT EXISTS memberships(username TEXT NOT NULL, tenant_id TEXT NOT NULL, role TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY(username, tenant_id))")
        con.execute("CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, name TEXT NOT NULL, description TEXT, created_at TEXT NOT NULL)")
        con.execute("CREATE TABLE IF NOT EXISTS boards(id TEXT PRIMARY KEY, project_id TEXT NOT NULL, name TEXT NOT NULL, created_at TEXT NOT NULL)")
        con.execute("CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY, board_id TEXT NOT NULL, column_name TEXT NOT NULL, title TEXT NOT NULL, content TEXT, assigned_user TEXT, due_date TEXT, priority TEXT, created_at TEXT NOT NULL)")
        con.execute("CREATE TABLE IF NOT EXISTS files(id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, name TEXT NOT NULL, path TEXT NOT NULL, size INTEGER NOT NULL, hash TEXT, created_at TEXT NOT NULL)")
        now = _ts()
        con.execute("INSERT OR REPLACE INTO tenants(tenant_id, display_name, created_at) VALUES (?,?,?)", (tenant_id, "KUKANILEA Demo Tenant", now))
        con.execute("INSERT OR REPLACE INTO users(username, password_hash, created_at) VALUES (?,?,?)", ("demo.admin", "seeded", now))
        con.execute("INSERT OR REPLACE INTO memberships(username, tenant_id, role, created_at) VALUES (?,?,?,?)", ("demo.admin", tenant_id, "ADMIN", now))
        project_ids = [str(uuid.uuid4()) for _ in range(3)]
        for idx, project_id in enumerate(project_ids, start=1):
            con.execute(
                "INSERT OR REPLACE INTO projects(id, tenant_id, name, description, created_at) VALUES (?,?,?,?,?)",
                (project_id, tenant_id, f"Projekt {idx}", f"Demo Projekt {idx}", _ts(-idx)),
            )
            board_id = str(uuid.uuid4())
            con.execute(
                "INSERT OR REPLACE INTO boards(id, project_id, name, created_at) VALUES (?,?,?,?)",
                (board_id, project_id, "Backlog", _ts(-idx)),
            )
            for task_no in range(1, 5):
                task_id = str(uuid.uuid4())
                con.execute(
                    """
                    INSERT OR REPLACE INTO tasks(id, board_id, column_name, title, content, assigned_user, due_date, priority, created_at)
                    VALUES (?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        task_id,
                        board_id,
                        "todo",
                        f"Task {idx}.{task_no}",
                        "Automatisch erzeugt für DR Drill",
                        "demo.admin",
                        _ts(task_no),
                        "medium",
                        _ts(-idx),
                    ),
                )

        for i in range(1, 4):
            con.execute(
                """
                INSERT OR REPLACE INTO files(id, tenant_id, name, path, size, hash, created_at)
                VALUES (?,?,?,?,?,?,?)
                """,
                (
                    str(uuid.uuid4()),
                    tenant_id,
                    f"dokument_{i}.pdf",
                    f"/docs/dokument_{i}.pdf",
                    2048 * i,
                    uuid.uuid4().hex,
                    _ts(-i),
                ),
            )
        con.commit()


def _seed_core(core_db_path: Path, tenant_id: str) -> None:
    core_db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(core_db_path) as con:
        con.execute("CREATE TABLE IF NOT EXISTS customers(id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, kdnr TEXT NOT NULL, name TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
        con.execute("CREATE TABLE IF NOT EXISTS time_projects(id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id TEXT NOT NULL, name TEXT NOT NULL, description TEXT, status TEXT NOT NULL DEFAULT 'ACTIVE', created_by TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
        con.execute("CREATE TABLE IF NOT EXISTS time_entries(id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id TEXT NOT NULL, project_id INTEGER, user TEXT NOT NULL, start_at TEXT NOT NULL, end_at TEXT, duration_seconds INTEGER, note TEXT, approval_status TEXT NOT NULL DEFAULT 'PENDING', approved_by TEXT, approved_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
        con.execute("CREATE TABLE IF NOT EXISTS docs(doc_id TEXT PRIMARY KEY, group_key TEXT NOT NULL, tenant_id TEXT, doctype TEXT, created_at TEXT NOT NULL)")
        con.execute("CREATE TABLE IF NOT EXISTS versions(id INTEGER PRIMARY KEY AUTOINCREMENT, doc_id TEXT NOT NULL, version_no INTEGER NOT NULL, bytes_sha256 TEXT NOT NULL, file_name TEXT NOT NULL, file_path TEXT NOT NULL, created_at TEXT NOT NULL, tenant_id TEXT)")

        project_ids = []
        for i in range(1, 3):
            con.execute(
                "INSERT INTO time_projects(tenant_id, name, description, status, created_by, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
                (tenant_id, f"Zeitprojekt {i}", "DR-Demo", "ACTIVE", "demo.admin", _ts(-i), _ts(-i)),
            )
            project_ids.append(con.execute("SELECT last_insert_rowid()").fetchone()[0])

        for i in range(1, 4):
            con.execute(
                "INSERT OR REPLACE INTO customers(id, tenant_id, kdnr, name, created_at, updated_at) VALUES (?,?,?,?,?,?)",
                (str(uuid.uuid4()), tenant_id, f"KD-{1000+i}", f"Kontakt {i}", _ts(-i), _ts(-i)),
            )

        for i in range(1, 6):
            start = datetime.utcnow() - timedelta(hours=i + 1)
            end = start + timedelta(minutes=30 + (i * 5))
            con.execute(
                """
                INSERT INTO time_entries(tenant_id, project_id, user, start_at, end_at, duration_seconds, note, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (
                    tenant_id,
                    project_ids[i % len(project_ids)],
                    "demo.admin",
                    start.isoformat(),
                    end.isoformat(),
                    int((end - start).total_seconds()),
                    "Seeded DR booking",
                    _ts(),
                    _ts(),
                ),
            )

        for i in range(1, 4):
            doc_id = uuid.uuid4().hex
            con.execute(
                "INSERT OR REPLACE INTO docs(doc_id, group_key, tenant_id, doctype, created_at) VALUES (?,?,?,?,?)",
                (doc_id, f"grp-{i}", tenant_id, "invoice", _ts(-i)),
            )
            con.execute(
                "INSERT INTO versions(doc_id, version_no, bytes_sha256, file_name, file_path, created_at, tenant_id) VALUES (?,?,?,?,?,?,?)",
                (doc_id, 1, uuid.uuid4().hex, f"dokument_{i}.pdf", f"/archive/dokument_{i}.pdf", _ts(-i), tenant_id),
            )
        con.commit()


def main() -> int:
    root = _data_root()
    root.mkdir(parents=True, exist_ok=True)
    tenant_id = os.environ.get("TENANT_ID", os.environ.get("TENANT_DEFAULT", "KUKANILEA"))
    auth_db = Path(os.environ.get("KUKANILEA_AUTH_DB", root / "auth.sqlite3"))
    core_db = Path(os.environ.get("KUKANILEA_CORE_DB", root / "core.sqlite3"))
    _seed_auth(auth_db, tenant_id)
    _seed_core(core_db, tenant_id)
    print(f"Seed complete for tenant={tenant_id} auth_db={auth_db} core_db={core_db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
