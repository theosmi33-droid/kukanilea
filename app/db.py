from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class User:
    username: str
    password_hash: str


@dataclass
class Tenant:
    tenant_id: str
    display_name: str


@dataclass
class Membership:
    username: str
    tenant_id: str
    role: str


class AuthDB:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _db(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self.path))
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL;")
        con.execute("PRAGMA synchronous=NORMAL;")
        con.execute("PRAGMA foreign_keys=ON;")
        con.execute("PRAGMA temp_store=MEMORY;")
        con.execute("PRAGMA cache_size=-64000;")
        con.execute("PRAGMA mmap_size=268435456;")
        return con

    def init(self) -> None:
        con = self._db()
        try:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS users(
                  username TEXT PRIMARY KEY,
                  password_hash TEXT NOT NULL,
                  created_at TEXT NOT NULL
                );
                """
            )
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS tenants(
                  tenant_id TEXT PRIMARY KEY,
                  display_name TEXT NOT NULL,
                  core_db_path TEXT,
                  created_at TEXT NOT NULL
                );
                """
            )
            try:
                con.execute("ALTER TABLE tenants ADD COLUMN core_db_path TEXT")
            except Exception:
                pass
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS memberships(
                  username TEXT NOT NULL,
                  tenant_id TEXT NOT NULL,
                  role TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  PRIMARY KEY(username, tenant_id),
                  FOREIGN KEY(username) REFERENCES users(username) ON DELETE CASCADE,
                  FOREIGN KEY(tenant_id) REFERENCES tenants(tenant_id) ON DELETE CASCADE
                );
                """
            )
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS meta(
                  key TEXT PRIMARY KEY,
                  value TEXT NOT NULL
                );
                """
            )
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_history(
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  ts TEXT NOT NULL,
                  tenant_id TEXT NOT NULL,
                  username TEXT NOT NULL,
                  role TEXT NOT NULL,
                  direction TEXT NOT NULL,
                  message TEXT NOT NULL
                );
                """
            )
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS projects(
                  id TEXT PRIMARY KEY,
                  tenant_id TEXT NOT NULL,
                  name TEXT NOT NULL,
                  description TEXT,
                  created_at TEXT NOT NULL,
                  FOREIGN KEY(tenant_id) REFERENCES tenants(tenant_id) ON DELETE CASCADE
                );
                """
            )
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS boards(
                  id TEXT PRIMARY KEY,
                  project_id TEXT NOT NULL,
                  name TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
                );
                """
            )
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks(
                  id TEXT PRIMARY KEY,
                  board_id TEXT NOT NULL,
                  column_name TEXT NOT NULL,
                  title TEXT NOT NULL,
                  content TEXT,
                  assigned_user TEXT,
                  due_date TEXT,
                  priority TEXT,
                  created_at TEXT NOT NULL,
                  FOREIGN KEY(board_id) REFERENCES boards(id) ON DELETE CASCADE
                );
                """
            )
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS files(
                  id TEXT PRIMARY KEY,
                  tenant_id TEXT NOT NULL,
                  name TEXT NOT NULL,
                  path TEXT NOT NULL,
                  size INTEGER NOT NULL,
                  hash TEXT, -- Phase 5: Integrity
                  keywords_json TEXT, -- Phase 3: YAKE!
                  frequency_score REAL DEFAULT 0.0, -- Phase 2: Scoring
                  version INTEGER DEFAULT 1,
                  created_at TEXT NOT NULL,
                  FOREIGN KEY(tenant_id) REFERENCES tenants(tenant_id) ON DELETE CASCADE
                );
                """
            )
            # Migration helper for v1.4
            for col, dtype in [("hash", "TEXT"), ("keywords_json", "TEXT"), ("frequency_score", "REAL")]:
                try: con.execute(f"ALTER TABLE files ADD COLUMN {col} {dtype}")
                except Exception: pass

            con.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_log(
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  ts TEXT NOT NULL,
                  tenant_id TEXT NOT NULL,
                  username TEXT NOT NULL,
                  action TEXT NOT NULL,
                  resource TEXT NOT NULL,
                  details TEXT
                );
                """
            )
            # Task 192: Immutable Audit Trail via Trigger
            con.execute(
                """
                CREATE TRIGGER IF NOT EXISTS prevent_audit_deletion
                BEFORE DELETE ON audit_log
                BEGIN
                    SELECT RAISE(FAIL, 'Audit log entries are immutable and cannot be deleted.');
                END;
                """
            )
            con.execute(
                """
                CREATE TRIGGER IF NOT EXISTS prevent_audit_update
                BEFORE UPDATE ON audit_log
                BEGIN
                    SELECT RAISE(FAIL, 'Audit log entries are immutable and cannot be modified.');
                END;
                """
            )
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS file_versions(
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  file_id TEXT NOT NULL,
                  version INTEGER NOT NULL,
                  path TEXT NOT NULL,
                  size INTEGER NOT NULL,
                  hash TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  FOREIGN KEY(file_id) REFERENCES files(id) ON DELETE CASCADE
                );
                """
            )
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS file_trash(
                  id TEXT PRIMARY KEY,
                  tenant_id TEXT NOT NULL,
                  original_name TEXT NOT NULL,
                  original_path TEXT NOT NULL,
                  deleted_at TEXT NOT NULL,
                  expires_at TEXT NOT NULL,
                  FOREIGN KEY(tenant_id) REFERENCES tenants(tenant_id) ON DELETE CASCADE
                );
                """
            )
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS task_relations(
                  task_id TEXT NOT NULL,
                  related_task_id TEXT NOT NULL,
                  relation_type TEXT NOT NULL, -- 'blocks', 'duplicate', 'relates'
                  PRIMARY KEY(task_id, related_task_id),
                  FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE,
                  FOREIGN KEY(related_task_id) REFERENCES tasks(id) ON DELETE CASCADE
                );
                """
            )
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS task_checklists(
                  id TEXT PRIMARY KEY,
                  task_id TEXT NOT NULL,
                  content TEXT NOT NULL,
                  is_done INTEGER DEFAULT 0,
                  FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
                );
                """
            )
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS automation_rules(
                  id TEXT PRIMARY KEY,
                  tenant_id TEXT NOT NULL,
                  trigger TEXT NOT NULL,
                  action TEXT NOT NULL,
                  config TEXT,
                  active INTEGER DEFAULT 1,
                  FOREIGN KEY(tenant_id) REFERENCES tenants(tenant_id) ON DELETE CASCADE
                );
                """
            )
            con.execute(
                "INSERT OR IGNORE INTO meta(key, value) VALUES ('schema_version', '3')"
            )
            con.commit()
        finally:
            con.close()

    def upsert_user(self, username: str, password_hash: str, created_at: str) -> None:
        con = self._db()
        try:
            con.execute(
                "INSERT OR REPLACE INTO users(username, password_hash, created_at) VALUES (?,?,?)",
                (username, password_hash, created_at),
            )
            con.commit()
        finally:
            con.close()

    def upsert_tenant(self, tenant_id: str, display_name: str, created_at: str) -> None:
        con = self._db()
        try:
            con.execute(
                "INSERT OR REPLACE INTO tenants(tenant_id, display_name, created_at) VALUES (?,?,?)",
                (tenant_id, display_name, created_at),
            )
            con.commit()
        finally:
            con.close()

    def upsert_membership(
        self, username: str, tenant_id: str, role: str, created_at: str
    ) -> None:
        con = self._db()
        try:
            con.execute(
                "INSERT OR REPLACE INTO memberships(username, tenant_id, role, created_at) VALUES (?,?,?,?)",
                (username, tenant_id, role, created_at),
            )
            con.commit()
        finally:
            con.close()

    def get_user(self, username: str) -> Optional[User]:
        con = self._db()
        try:
            row = con.execute(
                "SELECT username, password_hash FROM users WHERE username=?",
                (username,),
            ).fetchone()
            if not row:
                return None
            return User(username=row["username"], password_hash=row["password_hash"])
        finally:
            con.close()

    def get_memberships(self, username: str) -> List[Membership]:
        con = self._db()
        try:
            rows = con.execute(
                "SELECT username, tenant_id, role FROM memberships WHERE username=?",
                (username,),
            ).fetchall()
            return [
                Membership(
                    username=r["username"], tenant_id=r["tenant_id"], role=r["role"]
                )
                for r in rows
            ]
        finally:
            con.close()

    def get_tenant(self, tenant_id: str) -> Optional[Tenant]:
        con = self._db()
        try:
            row = con.execute(
                "SELECT tenant_id, display_name FROM tenants WHERE tenant_id=?",
                (tenant_id,),
            ).fetchone()
            if not row:
                return None
            return Tenant(tenant_id=row["tenant_id"], display_name=row["display_name"])
        finally:
            con.close()

    def get_schema_version(self) -> str:
        con = self._db()
        try:
            row = con.execute(
                "SELECT value FROM meta WHERE key='schema_version'"
            ).fetchone()
            return str(row["value"]) if row else "0"
        finally:
            con.close()

    def count_tenants(self) -> int:
        con = self._db()
        try:
            row = con.execute("SELECT COUNT(*) AS c FROM tenants").fetchone()
            return int(row["c"] or 0) if row else 0
        finally:
            con.close()

    def add_chat_message(
        self,
        *,
        ts: str,
        tenant_id: str,
        username: str,
        role: str,
        direction: str,
        message: str,
    ) -> None:
        con = self._db()
        try:
            con.execute(
                """
                INSERT INTO chat_history(ts, tenant_id, username, role, direction, message)
                VALUES (?,?,?,?,?,?)
                """,
                (ts, tenant_id, username, role, direction, message),
            )
            con.commit()
        finally:
            con.close()

    def list_chat_messages(self, *, tenant_id: str, limit: int = 50) -> List[dict]:
        con = self._db()
        try:
            rows = con.execute(
                """
                SELECT * FROM chat_history
                WHERE tenant_id=?
                ORDER BY id DESC
                LIMIT ?
                """,
                (tenant_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            con.close()
