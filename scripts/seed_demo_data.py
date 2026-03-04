#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _utc(offset_days: int = 0) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=offset_days)).isoformat()


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("PRAGMA foreign_keys=ON;")
    return con


def _ensure_schema(con: sqlite3.Connection) -> None:
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS tenants(
          tenant_id TEXT PRIMARY KEY,
          display_name TEXT NOT NULL,
          core_db_path TEXT,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS projects(
          id TEXT PRIMARY KEY,
          tenant_id TEXT NOT NULL,
          name TEXT NOT NULL,
          description TEXT,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS boards(
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL,
          name TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS tasks(
          id TEXT PRIMARY KEY,
          board_id TEXT NOT NULL,
          column_name TEXT NOT NULL,
          title TEXT NOT NULL,
          content TEXT,
          assigned_user TEXT,
          due_date TEXT,
          priority TEXT,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS files(
          id TEXT PRIMARY KEY,
          tenant_id TEXT NOT NULL,
          name TEXT NOT NULL,
          path TEXT NOT NULL,
          size INTEGER NOT NULL,
          hash TEXT,
          keywords_json TEXT,
          frequency_score REAL DEFAULT 0,
          version INTEGER DEFAULT 1,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS contacts(
          id TEXT PRIMARY KEY,
          tenant_id TEXT NOT NULL,
          full_name TEXT NOT NULL,
          email TEXT NOT NULL,
          phone TEXT,
          role TEXT,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS time_entries(
          id TEXT PRIMARY KEY,
          tenant_id TEXT NOT NULL,
          project_id TEXT NOT NULL,
          task_id TEXT,
          actor TEXT NOT NULL,
          minutes INTEGER NOT NULL,
          note TEXT,
          started_at TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        """
    )


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def seed_demo_data(db_path: Path, tenant_id: str = "DEMO_TENANT") -> dict:
    con = _connect(db_path)
    try:
        _ensure_schema(con)
        now = _utc(0)
        con.execute(
            """
            INSERT INTO tenants(tenant_id, display_name, core_db_path, created_at)
            VALUES(?,?,?,?)
            ON CONFLICT(tenant_id) DO UPDATE SET display_name=excluded.display_name
            """,
            (tenant_id, "Demo Restore Drill", str(db_path), now),
        )

        projects = [
            ("proj_demo_alpha", tenant_id, "Projekt Alpha", "Wärmepumpen-Rollout", now),
            ("proj_demo_beta", tenant_id, "Projekt Beta", "Service & Wartung", now),
        ]
        con.executemany(
            "INSERT OR REPLACE INTO projects(id, tenant_id, name, description, created_at) VALUES(?,?,?,?,?)",
            projects,
        )

        boards = [
            ("board_alpha", "proj_demo_alpha", "Kanban Alpha", now),
            ("board_beta", "proj_demo_beta", "Kanban Beta", now),
        ]
        con.executemany(
            "INSERT OR REPLACE INTO boards(id, project_id, name, created_at) VALUES(?,?,?,?)",
            boards,
        )

        tasks = [
            ("task_alpha_1", "board_alpha", "todo", "Kundenabnahme vorbereiten", "Checkliste finalisieren", "anna", _utc(5), "high", now),
            ("task_alpha_2", "board_alpha", "doing", "Material disponieren", "Bestellung 4711", "ben", _utc(2), "medium", now),
            ("task_beta_1", "board_beta", "done", "Wartungsprotokoll senden", "PDF versendet", "clara", _utc(-1), "low", now),
        ]
        con.executemany(
            """
            INSERT OR REPLACE INTO tasks(id, board_id, column_name, title, content, assigned_user, due_date, priority, created_at)
            VALUES(?,?,?,?,?,?,?,?,?)
            """,
            tasks,
        )

        contacts = [
            ("contact_1", tenant_id, "Mila Bauer", "mila.bauer@example.invalid", "+49-111-100", "Einkauf", now),
            ("contact_2", tenant_id, "Tariq Yildiz", "tariq.yildiz@example.invalid", "+49-111-101", "Technik", now),
            ("contact_3", tenant_id, "Eva Klein", "eva.klein@example.invalid", "+49-111-102", "Buchhaltung", now),
        ]
        con.executemany(
            "INSERT OR REPLACE INTO contacts(id, tenant_id, full_name, email, phone, role, created_at) VALUES(?,?,?,?,?,?,?)",
            contacts,
        )

        docs = [
            ("doc_1", tenant_id, "angebot_alpha.pdf", f"/vault/{tenant_id}/angebot_alpha.pdf", 18432, _hash_text("angebot_alpha"), json.dumps(["angebot", "alpha"]), 0.91, 3, now),
            ("doc_2", tenant_id, "wartung_beta.pdf", f"/vault/{tenant_id}/wartung_beta.pdf", 9321, _hash_text("wartung_beta"), json.dumps(["wartung", "beta"]), 0.62, 2, now),
        ]
        con.executemany(
            """
            INSERT OR REPLACE INTO files(id, tenant_id, name, path, size, hash, keywords_json, frequency_score, version, created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?)
            """,
            docs,
        )

        time_entries = [
            ("time_1", tenant_id, "proj_demo_alpha", "task_alpha_1", "anna", 90, "Kickoff vorbereitet", _utc(-2), now),
            ("time_2", tenant_id, "proj_demo_alpha", "task_alpha_2", "ben", 45, "Lieferant angerufen", _utc(-1), now),
            ("time_3", tenant_id, "proj_demo_beta", "task_beta_1", "clara", 30, "Protokoll erstellt", _utc(-1), now),
        ]
        con.executemany(
            """
            INSERT OR REPLACE INTO time_entries(id, tenant_id, project_id, task_id, actor, minutes, note, started_at, created_at)
            VALUES(?,?,?,?,?,?,?,?,?)
            """,
            time_entries,
        )
        con.commit()

        summary = {}
        summary["contacts"] = con.execute("SELECT COUNT(*) FROM contacts WHERE tenant_id=?", (tenant_id,)).fetchone()[0]
        summary["projects"] = con.execute("SELECT COUNT(*) FROM projects WHERE tenant_id=?", (tenant_id,)).fetchone()[0]
        summary["time_entries"] = con.execute("SELECT COUNT(*) FROM time_entries WHERE tenant_id=?", (tenant_id,)).fetchone()[0]
        summary["files"] = con.execute("SELECT COUNT(*) FROM files WHERE tenant_id=?", (tenant_id,)).fetchone()[0]
        summary["tasks"] = con.execute(
            """
            SELECT COUNT(*)
            FROM tasks t
            JOIN boards b ON b.id=t.board_id
            JOIN projects p ON p.id=b.project_id
            WHERE p.tenant_id=?
            """,
            (tenant_id,),
        ).fetchone()[0]
        return summary
    finally:
        con.close()


def main() -> int:
    db_path = Path(os.environ.get("KUKANILEA_AUTH_DB", "instance/auth.sqlite3"))
    tenant_id = os.environ.get("TENANT_ID", "DEMO_TENANT")
    summary = seed_demo_data(db_path, tenant_id)
    print(json.dumps({"ok": True, "tenant_id": tenant_id, "db": str(db_path), "counts": summary}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
