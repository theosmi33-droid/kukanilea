from __future__ import annotations

import secrets
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .rbac import (
    LEGACY_ROLE_ORDER,
    PERMISSION_DEFINITIONS,
    ROLE_DEFINITIONS,
    ROLE_PERMISSION_DEFAULTS,
    map_legacy_role_to_rbac,
    normalize_role_name,
)


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
            self._ensure_rbac_schema(con)
            self._ensure_user_preferences_schema(con)
            self._seed_rbac_defaults(con)
            self._sync_legacy_memberships_to_rbac(con)
            con.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES ('schema_version', '2')"
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
                sql = "ALTER TABLE users ADD COLUMN %s %s" % (col, decl)
                con.execute(sql)
        con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email)")

    def _ensure_rbac_schema(self, con: sqlite3.Connection) -> None:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS auth_roles(
              role_name TEXT PRIMARY KEY,
              label TEXT NOT NULL,
              description TEXT NOT NULL,
              is_system INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL
            );
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS auth_permissions(
              perm_key TEXT PRIMARY KEY,
              perm_label TEXT NOT NULL,
              perm_area TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS auth_role_permissions(
              role_name TEXT NOT NULL,
              perm_key TEXT NOT NULL,
              allowed INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL,
              PRIMARY KEY(role_name, perm_key),
              FOREIGN KEY(role_name) REFERENCES auth_roles(role_name) ON DELETE CASCADE,
              FOREIGN KEY(perm_key) REFERENCES auth_permissions(perm_key) ON DELETE CASCADE
            );
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS auth_user_roles(
              username TEXT NOT NULL,
              role_name TEXT NOT NULL,
              created_at TEXT NOT NULL,
              PRIMARY KEY(username, role_name),
              FOREIGN KEY(username) REFERENCES users(username) ON DELETE CASCADE,
              FOREIGN KEY(role_name) REFERENCES auth_roles(role_name) ON DELETE CASCADE
            );
            """
        )
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_auth_user_roles_user ON auth_user_roles(username)"
        )
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_auth_user_roles_role ON auth_user_roles(role_name)"
        )
        # Hard constraint for single-tenant owner model: only one OWNER_ADMIN row.
        con.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_auth_user_roles_single_owner_admin
            ON auth_user_roles(role_name)
            WHERE role_name='OWNER_ADMIN'
            """
        )

    def _ensure_user_preferences_schema(self, con: sqlite3.Connection) -> None:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS auth_user_preferences(
              username TEXT NOT NULL,
              pref_key TEXT NOT NULL,
              pref_value TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              PRIMARY KEY(username, pref_key)
            );
            """
        )
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_auth_user_preferences_user ON auth_user_preferences(username)"
        )

    def _seed_rbac_defaults(self, con: sqlite3.Connection) -> None:
        now = self._now_iso()
        for role_name, role in ROLE_DEFINITIONS.items():
            con.execute(
                """
                INSERT OR IGNORE INTO auth_roles(role_name, label, description, is_system, created_at)
                VALUES (?,?,?,?,?)
                """,
                (
                    role_name,
                    role.label,
                    role.description,
                    int(role.is_system),
                    now,
                ),
            )
        for perm_key, perm in PERMISSION_DEFINITIONS.items():
            con.execute(
                """
                INSERT OR IGNORE INTO auth_permissions(perm_key, perm_label, perm_area, created_at)
                VALUES (?,?,?,?)
                """,
                (perm_key, perm.label, perm.area, now),
            )
        con.execute(
            """
            INSERT OR IGNORE INTO auth_permissions(perm_key, perm_label, perm_area, created_at)
            VALUES ('*','Wildcard (DEV)','system',?)
            """,
            (now,),
        )
        for role_name, perm_keys in ROLE_PERMISSION_DEFAULTS.items():
            for perm_key in perm_keys:
                if perm_key != "*" and perm_key not in PERMISSION_DEFINITIONS:
                    continue
                con.execute(
                    """
                    INSERT OR REPLACE INTO auth_role_permissions(role_name, perm_key, allowed, created_at)
                    VALUES (?,?,1,?)
                    """,
                    (role_name, perm_key, now),
                )

    def _best_legacy_role_for_user(self, con: sqlite3.Connection, username: str) -> str:
        rows = con.execute(
            "SELECT role FROM memberships WHERE username=?",
            (username,),
        ).fetchall()
        best = "READONLY"
        for row in rows:
            role = str(row["role"] or "").strip().upper()
            if role not in LEGACY_ROLE_ORDER:
                continue
            if LEGACY_ROLE_ORDER.index(role) > LEGACY_ROLE_ORDER.index(best):
                best = role
        return best

    def _owner_usernames(self, con: sqlite3.Connection) -> list[str]:
        rows = con.execute(
            """
            SELECT ur.username
            FROM auth_user_roles ur
            LEFT JOIN users u ON u.username = ur.username
            WHERE ur.role_name='OWNER_ADMIN'
            ORDER BY COALESCE(u.created_at,''), ur.username
            """
        ).fetchall()
        return [str(r["username"]) for r in rows]

    def _sync_legacy_memberships_to_rbac(self, con: sqlite3.Connection) -> None:
        users = con.execute(
            "SELECT username FROM users ORDER BY COALESCE(created_at,''), username"
        ).fetchall()
        owners = self._owner_usernames(con)
        owner_assigned = bool(owners)
        now = self._now_iso()
        for row in users:
            username = str(row["username"] or "").strip()
            if not username:
                continue
            existing = con.execute(
                "SELECT role_name FROM auth_user_roles WHERE username=?",
                (username,),
            ).fetchall()
            if existing:
                continue
            legacy = self._best_legacy_role_for_user(con, username)
            mapped = map_legacy_role_to_rbac(legacy)
            if mapped == "OWNER_ADMIN":
                if owner_assigned:
                    mapped = "OFFICE"
                else:
                    owner_assigned = True
            con.execute(
                """
                INSERT OR IGNORE INTO auth_user_roles(username, role_name, created_at)
                VALUES (?,?,?)
                """,
                (username, mapped, now),
            )

        owners = self._owner_usernames(con)
        if not owners and users:
            primary = str(users[0]["username"])
            con.execute(
                """
                INSERT OR REPLACE INTO auth_user_roles(username, role_name, created_at)
                VALUES (?,?,?)
                """,
                (primary, "OWNER_ADMIN", now),
            )
            owners = [primary]

        if len(owners) > 1:
            keep = owners[0]
            for extra in owners[1:]:
                con.execute(
                    "DELETE FROM auth_user_roles WHERE username=? AND role_name='OWNER_ADMIN'",
                    (extra,),
                )
                remaining = con.execute(
                    "SELECT 1 FROM auth_user_roles WHERE username=? LIMIT 1",
                    (extra,),
                ).fetchone()
                if not remaining:
                    con.execute(
                        """
                        INSERT OR IGNORE INTO auth_user_roles(username, role_name, created_at)
                        VALUES (?,?,?)
                        """,
                        (extra, "OFFICE", now),
                    )
            con.execute(
                """
                INSERT OR IGNORE INTO auth_user_roles(username, role_name, created_at)
                VALUES (?,?,?)
                """,
                (keep, "OWNER_ADMIN", now),
            )

    def _now_iso(self) -> str:
        return (
            datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        )

    def _normalize_roles(self, roles: list[str]) -> list[str]:
        normalized: list[str] = []
        for role in roles:
            token = normalize_role_name(role)
            if token in ROLE_DEFINITIONS and token not in normalized:
                normalized.append(token)
        return normalized

    def _actor_can_manage_owner(self, actor_roles: list[str] | None) -> bool:
        roles = {normalize_role_name(r) for r in (actor_roles or [])}
        return "DEV" in roles or "OWNER_ADMIN" in roles

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

    def get_user(self, username: str) -> User | None:
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

    def get_user_by_email(self, email: str) -> User | None:
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

    def get_user_for_login(self, login: str) -> User | None:
        token = (login or "").strip()
        if not token:
            return None
        user = self.get_user(token.lower())
        if user:
            return user
        return self.get_user_by_email(token.lower())

    def get_memberships(self, username: str) -> list[Membership]:
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

    def list_users(self) -> list[dict[str, Any]]:
        con = self._db()
        try:
            rows = con.execute(
                """
                SELECT username, COALESCE(email,'') AS email, COALESCE(created_at,'') AS created_at
                FROM users
                ORDER BY COALESCE(created_at,''), username
                """
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            con.close()

    def list_roles(self) -> list[dict[str, Any]]:
        con = self._db()
        try:
            self._ensure_rbac_schema(con)
            self._seed_rbac_defaults(con)
            rows = con.execute(
                """
                SELECT role_name, label, description, is_system
                FROM auth_roles
                ORDER BY is_system DESC, role_name
                """
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            con.close()

    def list_permissions(self) -> list[dict[str, Any]]:
        con = self._db()
        try:
            self._ensure_rbac_schema(con)
            self._seed_rbac_defaults(con)
            rows = con.execute(
                """
                SELECT perm_key, perm_label, perm_area
                FROM auth_permissions
                ORDER BY perm_area, perm_key
                """
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            con.close()

    def get_role_permissions(self, role_name: str) -> set[str]:
        role = normalize_role_name(role_name)
        if role not in ROLE_DEFINITIONS:
            return set()
        con = self._db()
        try:
            self._ensure_rbac_schema(con)
            rows = con.execute(
                """
                SELECT perm_key
                FROM auth_role_permissions
                WHERE role_name=? AND allowed=1
                ORDER BY perm_key
                """,
                (role,),
            ).fetchall()
            return {str(r["perm_key"]) for r in rows}
        finally:
            con.close()

    def list_all_role_permissions(self) -> dict[str, set[str]]:
        con = self._db()
        try:
            self._ensure_rbac_schema(con)
            self._seed_rbac_defaults(con)
            out: dict[str, set[str]] = {role: set() for role in ROLE_DEFINITIONS}
            rows = con.execute(
                """
                SELECT role_name, perm_key
                FROM auth_role_permissions
                WHERE allowed=1
                """
            ).fetchall()
            for row in rows:
                role = normalize_role_name(str(row["role_name"] or ""))
                perm = str(row["perm_key"] or "")
                if role in out and perm:
                    out[role].add(perm)
            return out
        finally:
            con.close()

    def set_role_permissions(
        self,
        role_name: str,
        perm_keys: list[str],
        *,
        actor_roles: list[str] | None = None,
    ) -> None:
        role = normalize_role_name(role_name)
        if role not in ROLE_DEFINITIONS:
            raise ValueError("Unknown role.")
        actor = {normalize_role_name(r) for r in (actor_roles or [])}
        if "DEV" not in actor and "OWNER_ADMIN" not in actor:
            raise ValueError("Not allowed to manage permissions.")
        if role == "DEV" and "DEV" not in actor:
            raise ValueError("Only DEV can edit DEV role permissions.")

        allowed = {
            str(key).strip()
            for key in (perm_keys or [])
            if str(key).strip() in PERMISSION_DEFINITIONS or str(key).strip() == "*"
        }
        if role != "DEV":
            allowed.discard("*")

        con = self._db()
        try:
            self._ensure_rbac_schema(con)
            now = self._now_iso()
            con.execute("DELETE FROM auth_role_permissions WHERE role_name=?", (role,))
            for perm_key in sorted(allowed):
                con.execute(
                    """
                    INSERT INTO auth_role_permissions(role_name, perm_key, allowed, created_at)
                    VALUES (?,?,1,?)
                    """,
                    (role, perm_key, now),
                )
            con.commit()
        finally:
            con.close()

    def list_user_roles(
        self, username: str, *, ensure_default: bool = True
    ) -> list[str]:
        user = str(username or "").strip()
        if not user:
            return []
        con = self._db()
        try:
            self._ensure_rbac_schema(con)
            self._seed_rbac_defaults(con)
            rows = con.execute(
                "SELECT role_name FROM auth_user_roles WHERE username=? ORDER BY role_name",
                (user,),
            ).fetchall()
            roles = [normalize_role_name(str(r["role_name"] or "")) for r in rows]
            roles = [r for r in roles if r in ROLE_DEFINITIONS]
            if roles or not ensure_default:
                return roles
            exists = con.execute(
                "SELECT 1 FROM users WHERE username=? LIMIT 1",
                (user,),
            ).fetchone()
            if not exists:
                return []
            legacy = self._best_legacy_role_for_user(con, user)
            mapped = map_legacy_role_to_rbac(legacy)
            owners = self._owner_usernames(con)
            if mapped == "OWNER_ADMIN" and owners:
                mapped = "OFFICE"
            if not owners and mapped != "OWNER_ADMIN":
                mapped = "OWNER_ADMIN"
            con.execute(
                """
                INSERT OR IGNORE INTO auth_user_roles(username, role_name, created_at)
                VALUES (?,?,?)
                """,
                (user, mapped, self._now_iso()),
            )
            con.commit()
            return [mapped]
        finally:
            con.close()

    def set_user_roles(
        self,
        username: str,
        role_names: list[str],
        *,
        actor_roles: list[str] | None = None,
    ) -> None:
        user = str(username or "").strip()
        if not user:
            raise ValueError("Username required.")
        roles = self._normalize_roles(role_names)
        if not roles:
            raise ValueError("At least one role is required.")
        actor = {normalize_role_name(r) for r in (actor_roles or [])}
        if "DEV" not in actor and "OWNER_ADMIN" not in actor:
            raise ValueError("Not allowed to assign roles.")
        if any(r == "DEV" for r in roles) and "DEV" not in actor:
            raise ValueError("Only DEV can assign DEV role.")
        if "OWNER_ADMIN" in roles and not self._actor_can_manage_owner(list(actor)):
            raise ValueError("Not allowed to assign OWNER_ADMIN.")

        con = self._db()
        try:
            self._ensure_rbac_schema(con)
            user_row = con.execute(
                "SELECT username FROM users WHERE username=? LIMIT 1", (user,)
            ).fetchone()
            if not user_row:
                raise ValueError("Unknown user.")

            owners_before = set(self._owner_usernames(con))
            owners_after = set(owners_before)
            if user in owners_after:
                owners_after.remove(user)
            if "OWNER_ADMIN" in roles:
                owners_after.add(user)
            if len(owners_after) == 0:
                raise ValueError("At least one OWNER_ADMIN is required.")
            if len(owners_after) > 1:
                raise ValueError("Only one OWNER_ADMIN is allowed.")

            now = self._now_iso()
            con.execute("DELETE FROM auth_user_roles WHERE username=?", (user,))
            for role in roles:
                con.execute(
                    """
                    INSERT INTO auth_user_roles(username, role_name, created_at)
                    VALUES (?,?,?)
                    """,
                    (user, role, now),
                )
            con.commit()
        finally:
            con.close()

    def list_users_with_roles(self) -> list[dict[str, Any]]:
        con = self._db()
        try:
            self._ensure_rbac_schema(con)
            self._seed_rbac_defaults(con)
            users = self.list_users()
            rows = con.execute(
                "SELECT username, role_name FROM auth_user_roles ORDER BY username, role_name"
            ).fetchall()
            role_map: dict[str, list[str]] = {}
            for row in rows:
                username = str(row["username"] or "")
                role = normalize_role_name(str(row["role_name"] or ""))
                if role not in ROLE_DEFINITIONS:
                    continue
                role_map.setdefault(username, []).append(role)
            for item in users:
                username = str(item.get("username") or "")
                item["roles"] = role_map.get(username, [])
            return users
        finally:
            con.close()

    def get_effective_permissions(
        self, username: str, *, legacy_role: str = ""
    ) -> set[str]:
        roles = self.get_effective_roles(username, legacy_role=legacy_role)
        return self.get_effective_permissions_for_roles(roles)

    def get_effective_permissions_for_roles(self, role_names: list[str]) -> set[str]:
        roles = self._normalize_roles(role_names)
        if not roles:
            return set()
        if "DEV" in roles:
            return {"*"}
        con = self._db()
        try:
            self._ensure_rbac_schema(con)
            marks = ",".join("?" for _ in roles)
            rows = con.execute(
                f"""
                SELECT perm_key
                FROM auth_role_permissions
                WHERE role_name IN ({marks}) AND allowed=1
                """,
                tuple(roles),
            ).fetchall()
            return {str(r["perm_key"]) for r in rows}
        finally:
            con.close()

    def get_effective_roles(self, username: str, *, legacy_role: str = "") -> list[str]:
        roles = self.list_user_roles(username, ensure_default=True)
        if roles:
            return roles
        mapped = map_legacy_role_to_rbac(legacy_role)
        return [mapped]

    def get_user_preferences(
        self, username: str, *, keys: list[str] | None = None
    ) -> dict[str, str]:
        user = str(username or "").strip().lower()
        if not user:
            return {}
        con = self._db()
        try:
            self._ensure_user_preferences_schema(con)
            if keys:
                cleaned = [str(k or "").strip() for k in keys if str(k or "").strip()]
                if not cleaned:
                    return {}
                marks = ",".join("?" for _ in cleaned)
                rows = con.execute(
                    f"""
                    SELECT pref_key, pref_value
                    FROM auth_user_preferences
                    WHERE username=? AND pref_key IN ({marks})
                    """,
                    tuple([user, *cleaned]),
                ).fetchall()
            else:
                rows = con.execute(
                    """
                    SELECT pref_key, pref_value
                    FROM auth_user_preferences
                    WHERE username=?
                    """,
                    (user,),
                ).fetchall()
            return {str(r["pref_key"]): str(r["pref_value"] or "") for r in rows}
        finally:
            con.close()

    def set_user_preference(
        self, username: str, pref_key: str, pref_value: str
    ) -> None:
        user = str(username or "").strip().lower()
        key = str(pref_key or "").strip()
        if not user or not key:
            return
        con = self._db()
        try:
            self._ensure_user_preferences_schema(con)
            con.execute(
                """
                INSERT INTO auth_user_preferences(username, pref_key, pref_value, updated_at)
                VALUES (?,?,?,?)
                ON CONFLICT(username, pref_key) DO UPDATE SET
                  pref_value=excluded.pref_value,
                  updated_at=excluded.updated_at
                """,
                (user, key, str(pref_value or ""), self._now_iso()),
            )
            con.commit()
        finally:
            con.close()

    def ensure_user_rbac_roles(
        self, username: str, *, legacy_role: str = ""
    ) -> list[str]:
        return self.get_effective_roles(username, legacy_role=legacy_role)

    def user_has_permission(
        self, username: str, permission: str, *, legacy_role: str = ""
    ) -> bool:
        perm = str(permission or "").strip()
        if not perm:
            return False
        perms = self.get_effective_permissions(username, legacy_role=legacy_role)
        return "*" in perms or perm in perms

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
    ) -> str | None:
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
    ) -> str | None:
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

    def list_outbox(self, limit: int = 20) -> list[dict[str, Any]]:
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

    def get_tenant(self, tenant_id: str) -> Tenant | None:
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

    def list_chat_messages(self, *, tenant_id: str, limit: int = 50) -> list[dict]:
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
