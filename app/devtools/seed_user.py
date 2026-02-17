from __future__ import annotations

import argparse
import secrets
from datetime import datetime

from app.auth import hash_password
from app.config import Config
from app.db import AuthDB


def _username_from_email(db: AuthDB, email: str) -> str:
    base = (email.split("@", 1)[0] or "user").lower().replace(".", "_")
    base = "".join(c for c in base if c.isalnum() or c in {"_", "-"})
    if not base:
        base = "user"
    candidate = base
    idx = 1
    while db.get_user(candidate) is not None:
        idx += 1
        candidate = f"{base}_{idx}"
    return candidate


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed one local auth user.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--role", default="OPERATOR")
    parser.add_argument("--password", default="")
    parser.add_argument("--verified", action="store_true")
    args = parser.parse_args()

    db = AuthDB(Config.AUTH_DB)
    db.init()
    email = str(args.email).strip().lower()
    tenant = str(args.tenant).strip()
    now = datetime.utcnow().isoformat(timespec="seconds")
    db.upsert_tenant(tenant, tenant, now)

    existing = db.get_user_by_email(email)
    if existing is not None:
        username = existing.username
        pwd = str(args.password or "")
        if pwd:
            db.reset_password(username, hash_password(pwd), now)
        db.upsert_membership(username, tenant, str(args.role), now)
        print(f"updated user={username} email={email} tenant={tenant} role={args.role}")
        return

    password = str(args.password or "").strip() or secrets.token_urlsafe(12)
    username = _username_from_email(db, email)
    db.create_user(
        username=username,
        password_hash=hash_password(password),
        created_at=now,
        email=email,
        email_verified=1 if args.verified else 0,
    )
    db.upsert_membership(username, tenant, str(args.role), now)
    print(
        f"created user={username} email={email} tenant={tenant} role={args.role} password={password}"
    )


if __name__ == "__main__":
    main()
