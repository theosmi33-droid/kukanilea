import os
from pathlib import Path

from app.db import AuthDB
from app.auth import hash_password


def test_seed_users(tmp_path):
    db_path = tmp_path / "auth.db"
    db = AuthDB(db_path)
    db.init()
    now = "2024-01-01T00:00:00"
    db.upsert_tenant("KUKANILEA", "KUKANILEA", now)
    db.upsert_tenant("KUKANILEA Dev", "KUKANILEA Dev", now)
    db.upsert_user("admin", hash_password("admin"), now)
    db.upsert_user("dev", hash_password("dev"), now)
    db.upsert_membership("admin", "KUKANILEA", "ADMIN", now)
    db.upsert_membership("dev", "KUKANILEA Dev", "DEV", now)

    admin = db.get_user("admin")
    dev = db.get_user("dev")
    assert admin is not None
    assert dev is not None
    memberships = db.get_memberships("admin")
    assert memberships[0].tenant_id == "KUKANILEA"
