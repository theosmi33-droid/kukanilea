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
        con.execute("PRAGMA foreign_keys=ON;")
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
                  created_at TEXT NOT NULL
                );
                """
            )
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
            con.execute("INSERT OR IGNORE INTO meta(key, value) VALUES ('schema_version', '1')")
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

    def upsert_membership(self, username: str, tenant_id: str, role: str, created_at: str) -> None:
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
            row = con.execute("SELECT username, password_hash FROM users WHERE username=?", (username,)).fetchone()
            if not row:
                return None
            return User(username=row["username"], password_hash=row["password_hash"])
        finally:
            con.close()

    def get_memberships(self, username: str) -> List[Membership]:
        con = self._db()
        try:
            rows = con.execute(
                "SELECT username, tenant_id, role FROM memberships WHERE username=?", (username,)
            ).fetchall()
            return [Membership(username=r["username"], tenant_id=r["tenant_id"], role=r["role"]) for r in rows]
        finally:
            con.close()

    def get_tenant(self, tenant_id: str) -> Optional[Tenant]:
        con = self._db()
        try:
            row = con.execute("SELECT tenant_id, display_name FROM tenants WHERE tenant_id=?", (tenant_id,)).fetchone()
            if not row:
                return None
            return Tenant(tenant_id=row["tenant_id"], display_name=row["display_name"])
        finally:
            con.close()

    def get_schema_version(self) -> str:
        con = self._db()
        try:
            row = con.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
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
