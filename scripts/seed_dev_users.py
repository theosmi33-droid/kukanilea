from __future__ import annotations

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

    print("Seeded users: admin/admin (KUKANILEA), dev/dev (KUKANILEA Dev)")


if __name__ == "__main__":
    main()
