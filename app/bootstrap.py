from __future__ import annotations

import ipaddress
import secrets
from datetime import datetime, timezone

from .auth import hash_password
from .db import AuthDB


def _now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def is_localhost_addr(remote_addr: str | None) -> bool:
    value = str(remote_addr or "").strip()
    if not value:
        return False
    try:
        return ipaddress.ip_address(value).is_loopback
    except ValueError:
        return False


def needs_bootstrap(auth_db: AuthDB) -> bool:
    counter = getattr(auth_db, "user_count", None)
    if callable(counter):
        return int(counter()) == 0
    con = auth_db._db()  # pragma: no cover - compatibility for legacy AuthDB
    try:
        row = con.execute("SELECT COUNT(*) AS c FROM users").fetchone()
        if not row:
            return True
        return int(row["c"] or 0) == 0
    finally:
        con.close()


def bootstrap_dev_user(
    auth_db: AuthDB, *, tenant_id: str = "KUKANILEA", tenant_name: str = "KUKANILEA"
) -> dict[str, str]:
    if not needs_bootstrap(auth_db):
        raise RuntimeError("Bootstrap not allowed: users already exist.")

    now = _now_iso()
    tenant = str(tenant_id or "").strip() or "KUKANILEA"
    display_name = str(tenant_name or "").strip() or tenant
    username = "dev"
    email = "dev@localhost.invalid"
    password = secrets.token_urlsafe(16)

    auth_db.create_user(
        username=username,
        password_hash=hash_password(password),
        created_at=now,
        email=email,
        email_verified=1,
    )
    auth_db.upsert_tenant(tenant, display_name, now)
    auth_db.upsert_membership(username, tenant, "DEV", now)
    return {
        "username": username,
        "password": password,
        "tenant_id": tenant,
        "email": email,
    }
