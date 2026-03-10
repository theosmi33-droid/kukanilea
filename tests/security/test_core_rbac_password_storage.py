from __future__ import annotations

from pathlib import Path

from app.core import logic


def test_rbac_create_user_stores_pbkdf2_hash(tmp_path: Path):
    db_path = tmp_path / "core.sqlite3"
    old_db_path = logic.DB_PATH
    try:
        logic.set_db_path(db_path)
        logic.rbac_create_user("alice", "secret-pass")

        con = logic._db()
        try:
            row = con.execute(
                "SELECT pass_sha256 FROM users WHERE username=?", ("alice",)
            ).fetchone()
            assert row is not None
            stored = str(row["pass_sha256"])
            assert stored.startswith("pbkdf2_sha256$")
        finally:
            con.close()
    finally:
        logic.set_db_path(old_db_path)


def test_rbac_verify_user_accepts_legacy_sha256_and_rehashes(tmp_path: Path):
    db_path = tmp_path / "core.sqlite3"
    old_db_path = logic.DB_PATH
    try:
        logic.set_db_path(db_path)
        legacy_hash = logic._sha256_bytes(b"legacy-pass")

        con = logic._db()
        try:
            con.execute(
                "INSERT INTO users(username, pass_sha256, created_at) VALUES (?,?,?)",
                ("legacy", legacy_hash, logic._now_iso()),
            )
            con.commit()
        finally:
            con.close()

        assert logic.rbac_verify_user("legacy", "legacy-pass") is True

        con = logic._db()
        try:
            row = con.execute(
                "SELECT pass_sha256 FROM users WHERE username=?", ("legacy",)
            ).fetchone()
            assert row is not None
            upgraded = str(row["pass_sha256"])
            assert upgraded.startswith("pbkdf2_sha256$")
            assert upgraded != legacy_hash
        finally:
            con.close()
    finally:
        logic.set_db_path(old_db_path)
