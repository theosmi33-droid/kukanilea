from __future__ import annotations

import secrets
from datetime import datetime

from app.auth import hash_password
from app.config import Config
from app.db import AuthDB


def main() -> None:
    db = AuthDB(Config.AUTH_DB)
    db.init()
    now = datetime.utcnow().isoformat()

    db.upsert_tenant("KUKANILEA", "KUKANILEA", now)
    db.upsert_tenant("KUKANILEA Dev", "KUKANILEA Dev", now)

    db.upsert_user("admin", hash_password("admin"), now)
    db.upsert_user("dev", hash_password("dev"), now)

    db.upsert_membership("admin", "KUKANILEA", "ADMIN", now)
    db.upsert_membership("dev", "KUKANILEA Dev", "DEV", now)
    office_email = "theosmi33@gmail.com"
    office_msg = "office user unchanged"
    if db.get_user_by_email(office_email) is None:
        office_password = secrets.token_urlsafe(12)
        office_username = "office"
        if db.get_user(office_username) is not None:
            office_username = f"office_{secrets.randbelow(1000)}"
        db.create_user(
            username=office_username,
            password_hash=hash_password(office_password),
            created_at=now,
            email=office_email,
            email_verified=1,
        )
        db.upsert_membership(office_username, "KUKANILEA Dev", "OPERATOR", now)
        office_msg = f"office user {office_email} password: {office_password}"

    print(
        "Seeded users: admin/admin (KUKANILEA), dev/dev (KUKANILEA Dev), " + office_msg
    )


if __name__ == "__main__":
    main()
