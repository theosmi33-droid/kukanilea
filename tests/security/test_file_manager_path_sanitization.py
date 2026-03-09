from __future__ import annotations

import sqlite3
from pathlib import Path

from app.modules.files.logic import FileManager


class _DBStub:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._init()

    def _db(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self.path))
        con.row_factory = sqlite3.Row
        return con

    def _init(self) -> None:
        con = self._db()
        try:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS files(
                  id TEXT PRIMARY KEY,
                  tenant_id TEXT NOT NULL,
                  name TEXT NOT NULL,
                  path TEXT NOT NULL,
                  size INTEGER NOT NULL,
                  version INTEGER NOT NULL,
                  created_at TEXT NOT NULL
                )
                """
            )
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS file_versions(
                  file_id TEXT NOT NULL,
                  version INTEGER NOT NULL,
                  path TEXT NOT NULL,
                  size INTEGER NOT NULL,
                  hash TEXT NOT NULL,
                  created_at TEXT NOT NULL
                )
                """
            )
            con.commit()
        finally:
            con.close()


def test_file_manager_upload_sanitizes_path_components(tmp_path: Path):
    db = _DBStub(tmp_path / "auth.sqlite3")
    manager = FileManager(db, tmp_path)

    file_id = manager.upload_file(
        tenant_id="../tenant-a",
        filename="../../evil.txt",
        content=b"abc",
    )
    assert file_id

    con = db._db()
    try:
        row = con.execute("SELECT path FROM files WHERE id = ?", (file_id,)).fetchone()
        assert row is not None
        stored_path = Path(row["path"]).resolve()
    finally:
        con.close()

    vault_root = (tmp_path / "vault").resolve()
    assert str(stored_path).startswith(str(vault_root))
    assert ".." not in stored_path.as_posix()
    assert stored_path.name.endswith("_evil.txt")

