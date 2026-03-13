from __future__ import annotations

import secrets
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def main() -> None:
    from app.auth import hash_password
    from app.config import Config
    from app.db import AuthDB

    db = AuthDB(Config.AUTH_DB)
    db.init()
    now = datetime.now(UTC).isoformat()
    admin_password = secrets.token_urlsafe(18)
    dev_password = secrets.token_urlsafe(18)

    db.upsert_tenant("KUKANILEA", "KUKANILEA", now)
    db.upsert_tenant("KUKANILEA Dev", "KUKANILEA Dev", now)

    db.upsert_user("admin", hash_password(admin_password), now)
    db.upsert_user("dev", hash_password(dev_password), now)

    db.upsert_membership("admin", "KUKANILEA", "ADMIN", now)
    db.upsert_membership("dev", "KUKANILEA", "DEV", now)

    print(
        "Seeded users (local/dev only): "
        f"admin/{admin_password} (KUKANILEA), "
        f"dev/{dev_password} (KUKANILEA)"
    )


if __name__ == "__main__":
    main()
