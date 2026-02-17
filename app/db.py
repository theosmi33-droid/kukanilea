from __future__ import annotations

import secrets
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional


@dataclass
class User:
    username: str
    password_hash: str
    email: str = ""
    email_verified: int = 0


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
            self._ensure_user_schema(con)
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
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_history(
                  id TEXT PRIMARY KEY,
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
                CREATE TABLE IF NOT EXISTS auth_outbox(
                  id TEXT PRIMARY KEY,
                  tenant_id TEXT NOT NULL DEFAULT 'KUKANILEA',
                  kind TEXT NOT NULL,
                  recipient_redacted TEXT NOT NULL,
                  subject TEXT NOT NULL,
                  body TEXT NOT NULL,
                  created_at TEXT NOT NULL
                );
                """
            )
            self._ensure_outbox_schema(con)
            con.execute(
                "INSERT OR IGNORE INTO meta(key, value) VALUES ('schema_version', '1')"
            )
            con.commit()
        finally:
            con.close()

    def _ensure_outbox_schema(self, con: sqlite3.Connection) -> None:
        rows = con.execute("PRAGMA table_info(auth_outbox)").fetchall()
        existing = {str(r["name"]) for r in rows}
        if "tenant_id" not in existing:
            con.execute(
                "ALTER TABLE auth_outbox ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'KUKANILEA'"
            )

    def _ensure_user_schema(self, con: sqlite3.Connection) -> None:
        rows = con.execute("PRAGMA table_info(users)").fetchall()
        existing = {str(r["name"]) for r in rows}
        wanted: list[tuple[str, str]] = [
            ("email", "TEXT"),
            ("email_verified", "INTEGER NOT NULL DEFAULT 0"),
            ("email_verify_code", "TEXT"),
            ("email_verify_expires_at", "TEXT"),
            ("reset_code", "TEXT"),
            ("reset_expires_at", "TEXT"),
            ("updated_at", "TEXT"),
        ]
        for col, decl in wanted:
            if col not in existing:
                con.execute(f"ALTER TABLE users ADD COLUMN {col} {decl}")
        con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email)")

    def upsert_user(self, username: str, password_hash: str, created_at: str) -> None:
        con = self._db()
        try:
            con.execute(
                """
                INSERT INTO users(username, password_hash, created_at, updated_at)
                VALUES (?,?,?,?)
                ON CONFLICT(username) DO UPDATE SET
                  password_hash=excluded.password_hash,
                  updated_at=excluded.updated_at
                """,
                (username, password_hash, created_at, created_at),
            )
            con.commit()
        finally:
            con.close()

    def create_user(
        self,
        *,
        username: str,
        password_hash: str,
        created_at: str,
        email: str = "",
        email_verified: int = 0,
    ) -> None:
        con = self._db()
        try:
            con.execute(
                """
                INSERT INTO users(
                  username, password_hash, created_at, updated_at, email, email_verified
                )
                VALUES (?,?,?,?,?,?)
                """,
                (
                    username,
                    password_hash,
                    created_at,
                    created_at,
                    email,
                    int(email_verified),
                ),
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
                """
                SELECT username, password_hash, COALESCE(email,'') AS email,
                       COALESCE(email_verified,0) AS email_verified
                FROM users
                WHERE username=?
                """,
                (username,),
            ).fetchone()
            if not row:
                return None
            return User(
                username=row["username"],
                password_hash=row["password_hash"],
                email=str(row["email"] or ""),
                email_verified=int(row["email_verified"] or 0),
            )
        finally:
            con.close()

    def get_user_by_email(self, email: str) -> Optional[User]:
        con = self._db()
        try:
            row = con.execute(
                """
                SELECT username, password_hash, COALESCE(email,'') AS email,
                       COALESCE(email_verified,0) AS email_verified
                FROM users
                WHERE LOWER(COALESCE(email,''))=LOWER(?)
                """,
                (email,),
            ).fetchone()
            if not row:
                return None
            return User(
                username=row["username"],
                password_hash=row["password_hash"],
                email=str(row["email"] or ""),
                email_verified=int(row["email_verified"] or 0),
            )
        finally:
            con.close()

    def get_user_for_login(self, login: str) -> Optional[User]:
        token = (login or "").strip()
        if not token:
            return None
        user = self.get_user(token.lower())
        if user:
            return user
        return self.get_user_by_email(token.lower())

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

    def set_email_verification_code(
        self, username: str, code_hash: str, expires_at: str, now_iso: str
    ) -> None:
        con = self._db()
        try:
            con.execute(
                """
                UPDATE users
                SET email_verify_code=?, email_verify_expires_at=?, updated_at=?
                WHERE username=?
                """,
                (code_hash, expires_at, now_iso, username),
            )
            con.commit()
        finally:
            con.close()

    def mark_email_verified(self, username: str, now_iso: str) -> None:
        con = self._db()
        try:
            con.execute(
                """
                UPDATE users
                SET email_verified=1,
                    email_verify_code=NULL,
                    email_verify_expires_at=NULL,
                    updated_at=?
                WHERE username=?
                """,
                (now_iso, username),
            )
            con.commit()
        finally:
            con.close()

    def get_user_by_email_verify_code(
        self, email: str, code_hash: str, now_iso: str
    ) -> Optional[str]:
        con = self._db()
        try:
            row = con.execute(
                """
                SELECT username, COALESCE(email_verify_code,'') AS verify_hash
                FROM users
                WHERE LOWER(COALESCE(email,''))=LOWER(?)
                  AND COALESCE(email_verify_expires_at,'')>=?
                LIMIT 1
                """,
                (email, now_iso),
            ).fetchone()
            if not row:
                return None
            stored = str(row["verify_hash"] or "")
            if not stored or not secrets.compare_digest(stored, str(code_hash or "")):
                return None
            return str(row["username"])
        finally:
            con.close()

    def set_password_reset_code(
        self, email: str, code_hash: str, expires_at: str, now_iso: str
    ) -> None:
        con = self._db()
        try:
            con.execute(
                """
                UPDATE users
                SET reset_code=?, reset_expires_at=?, updated_at=?
                WHERE LOWER(COALESCE(email,''))=LOWER(?)
                """,
                (code_hash, expires_at, now_iso, email),
            )
            con.commit()
        finally:
            con.close()

    def get_user_by_reset_code(
        self, email: str, code_hash: str, now_iso: str
    ) -> Optional[str]:
        con = self._db()
        try:
            row = con.execute(
                """
                SELECT username, COALESCE(reset_code,'') AS reset_hash
                FROM users
                WHERE LOWER(COALESCE(email,''))=LOWER(?)
                  AND COALESCE(reset_expires_at,'')>=?
                LIMIT 1
                """,
                (email, now_iso),
            ).fetchone()
            if not row:
                return None
            stored = str(row["reset_hash"] or "")
            if not stored or not secrets.compare_digest(stored, str(code_hash or "")):
                return None
            return str(row["username"])
        finally:
            con.close()

    def reset_password(self, username: str, password_hash: str, now_iso: str) -> None:
        con = self._db()
        try:
            con.execute(
                """
                UPDATE users
                SET password_hash=?,
                    reset_code=NULL,
                    reset_expires_at=NULL,
                    updated_at=?
                WHERE username=?
                """,
                (password_hash, now_iso, username),
            )
            con.commit()
        finally:
            con.close()

    def add_outbox(
        self,
        *,
        tenant_id: str = "KUKANILEA",
        kind: str,
        recipient_redacted: str,
        subject: str,
        body: str,
        created_at: str,
    ) -> None:
        con = self._db()
        try:
            con.execute(
                """
                INSERT INTO auth_outbox(id, tenant_id, kind, recipient_redacted, subject, body, created_at)
                VALUES (?,?,?,?,?,?,?)
                """,
                (
                    uuid.uuid4().hex,
                    tenant_id,
                    kind,
                    recipient_redacted,
                    subject,
                    body,
                    created_at,
                ),
            )
            con.commit()
        finally:
            con.close()

    def list_outbox(self, limit: int = 20) -> List[dict[str, Any]]:
        lim = max(1, min(int(limit or 20), 200))
        con = self._db()
        try:
            rows = con.execute(
                """
                SELECT id, tenant_id, kind, recipient_redacted, subject, body, created_at
                FROM auth_outbox
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (lim,),
            ).fetchall()
            return [dict(r) for r in rows]
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
                INSERT INTO chat_history(id, ts, tenant_id, username, role, direction, message)
                VALUES (?,?,?,?,?,?,?)
                """,
                (uuid.uuid4().hex, ts, tenant_id, username, role, direction, message),
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
                ORDER BY ts DESC, id DESC
                LIMIT ?
                """,
                (tenant_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            con.close()
