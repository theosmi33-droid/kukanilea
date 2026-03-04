#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _utc(offset_days: int = 0, hour: int = 9) -> str:
    base = datetime.now(timezone.utc).replace(hour=hour, minute=0, second=0, microsecond=0)
    return (base + timedelta(days=offset_days)).isoformat()


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
        CREATE UNIQUE INDEX IF NOT EXISTS idx_contacts_tenant_email
          ON contacts(tenant_id, email);
        CREATE INDEX IF NOT EXISTS idx_tasks_board_column
          ON tasks(board_id, column_name);
        CREATE INDEX IF NOT EXISTS idx_files_tenant_name
          ON files(tenant_id, name);
        """
    )


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _upsert_many(con: sqlite3.Connection, table: str, columns: list[str], rows: list[tuple]) -> None:
    assignments = ", ".join(f"{col}=excluded.{col}" for col in columns[1:])
    placeholders = ",".join(["?"] * len(columns))
    col_sql = ", ".join(columns)
    con.executemany(
        f"INSERT INTO {table}({col_sql}) VALUES({placeholders}) ON CONFLICT({columns[0]}) DO UPDATE SET {assignments}",
        rows,
    )


def seed_demo_data(db_path: Path, tenant_id: str = "DEMO_TENANT") -> dict:
    con = _connect(db_path)
    try:
        _ensure_schema(con)
        created_at = _utc(0)
        con.execute(
            """
            INSERT INTO tenants(tenant_id, display_name, core_db_path, created_at)
            VALUES(?,?,?,?)
            ON CONFLICT(tenant_id) DO UPDATE SET
              display_name=excluded.display_name,
              core_db_path=excluded.core_db_path
            """,
            (tenant_id, "Demo Restore Drill", str(db_path), created_at),
        )

        projects = [
            ("proj_demo_alpha", tenant_id, "Projekt Alpha", "Wärmepumpen-Rollout", created_at),
            ("proj_demo_beta", tenant_id, "Projekt Beta", "Service & Wartung", created_at),
            ("proj_demo_gamma", tenant_id, "Projekt Gamma", "IoT Sensorik Upgrade", created_at),
        ]
        _upsert_many(con, "projects", ["id", "tenant_id", "name", "description", "created_at"], projects)

        boards = [
            ("board_alpha", "proj_demo_alpha", "Kanban Alpha", created_at),
            ("board_beta", "proj_demo_beta", "Kanban Beta", created_at),
            ("board_gamma", "proj_demo_gamma", "Kanban Gamma", created_at),
        ]
        _upsert_many(con, "boards", ["id", "project_id", "name", "created_at"], boards)

        tasks = [
            ("task_alpha_1", "board_alpha", "todo", "Kundenabnahme vorbereiten", "Checkliste finalisieren", "anna", _utc(5), "high", created_at),
            ("task_alpha_2", "board_alpha", "doing", "Material disponieren", "Bestellung 4711", "ben", _utc(2), "medium", created_at),
            ("task_beta_1", "board_beta", "done", "Wartungsprotokoll senden", "PDF versendet", "clara", _utc(-1), "low", created_at),
            ("task_beta_2", "board_beta", "todo", "Folgetermin planen", "Kalenderabgleich mit Kunde", "david", _utc(4), "medium", created_at),
            ("task_gamma_1", "board_gamma", "doing", "Gateway Firmware validieren", "Labortest und Rollback-Plan", "elena", _utc(1), "high", created_at),
            ("task_gamma_2", "board_gamma", "review", "Anomalie-Report prüfen", "Messwerte gegen Baseline vergleichen", "felix", _utc(3), "high", created_at),
        ]
        _upsert_many(
            con,
            "tasks",
            ["id", "board_id", "column_name", "title", "content", "assigned_user", "due_date", "priority", "created_at"],
            tasks,
        )

        contacts = [
            ("contact_1", tenant_id, "Mila Bauer", "mila.bauer@example.invalid", "+49-111-100", "Einkauf", created_at),
            ("contact_2", tenant_id, "Tariq Yildiz", "tariq.yildiz@example.invalid", "+49-111-101", "Technik", created_at),
            ("contact_3", tenant_id, "Eva Klein", "eva.klein@example.invalid", "+49-111-102", "Buchhaltung", created_at),
            ("contact_4", tenant_id, "Luca Schwarz", "luca.schwarz@example.invalid", "+49-111-103", "Operations", created_at),
        ]
        _upsert_many(con, "contacts", ["id", "tenant_id", "full_name", "email", "phone", "role", "created_at"], contacts)

        docs = [
            ("doc_1", tenant_id, "angebot_alpha.pdf", f"/vault/{tenant_id}/angebot_alpha.pdf", 18432, _hash_text("angebot_alpha"), json.dumps(["angebot", "alpha"]), 0.91, 3, created_at),
            ("doc_2", tenant_id, "wartung_beta.pdf", f"/vault/{tenant_id}/wartung_beta.pdf", 9321, _hash_text("wartung_beta"), json.dumps(["wartung", "beta"]), 0.62, 2, created_at),
            ("doc_3", tenant_id, "sensorik_gamma.xlsx", f"/vault/{tenant_id}/sensorik_gamma.xlsx", 27310, _hash_text("sensorik_gamma"), json.dumps(["iot", "messung", "gamma"]), 0.74, 5, created_at),
        ]
        _upsert_many(
            con,
            "files",
            ["id", "tenant_id", "name", "path", "size", "hash", "keywords_json", "frequency_score", "version", "created_at"],
            docs,
        )

        time_entries = [
            ("time_1", tenant_id, "proj_demo_alpha", "task_alpha_1", "anna", 90, "Kickoff vorbereitet", _utc(-2, hour=10), created_at),
            ("time_2", tenant_id, "proj_demo_alpha", "task_alpha_2", "ben", 45, "Lieferant angerufen", _utc(-1, hour=8), created_at),
            ("time_3", tenant_id, "proj_demo_beta", "task_beta_1", "clara", 30, "Protokoll erstellt", _utc(-1, hour=14), created_at),
            ("time_4", tenant_id, "proj_demo_gamma", "task_gamma_1", "elena", 120, "Firmware-Testplan und Rückfallstrategie", _utc(0, hour=11), created_at),
            ("time_5", tenant_id, "proj_demo_gamma", "task_gamma_2", "felix", 55, "Messabweichungen dokumentiert", _utc(0, hour=15), created_at),
        ]
        _upsert_many(
            con,
            "time_entries",
            ["id", "tenant_id", "project_id", "task_id", "actor", "minutes", "note", "started_at", "created_at"],
            time_entries,
        )

        con.commit()

        return {
            "tenant": con.execute("SELECT COUNT(*) FROM tenants WHERE tenant_id=?", (tenant_id,)).fetchone()[0],
            "contacts": con.execute("SELECT COUNT(*) FROM contacts WHERE tenant_id=?", (tenant_id,)).fetchone()[0],
            "projects": con.execute("SELECT COUNT(*) FROM projects WHERE tenant_id=?", (tenant_id,)).fetchone()[0],
            "time_entries": con.execute("SELECT COUNT(*) FROM time_entries WHERE tenant_id=?", (tenant_id,)).fetchone()[0],
            "documents": con.execute("SELECT COUNT(*) FROM files WHERE tenant_id=?", (tenant_id,)).fetchone()[0],
            "tasks": con.execute(
                """
                SELECT COUNT(*)
                FROM tasks t
                JOIN boards b ON b.id=t.board_id
                JOIN projects p ON p.id=b.project_id
                WHERE p.tenant_id=?
                """,
                (tenant_id,),
            ).fetchone()[0],
        }
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
