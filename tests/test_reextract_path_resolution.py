from __future__ import annotations

import importlib
import sqlite3
from pathlib import Path

import pytest

CORE_MODULES = ["kukanilea_core", "kukanilea_core_v3_fixed"]


def _has_column(con: sqlite3.Connection, table: str, column: str) -> bool:
    rows = con.execute(f"PRAGMA table_info({table})").fetchall()
    return any(str(r[1]) == column for r in rows)


def _setup_core(module_name: str, tmp_path: Path):
    core = importlib.import_module(module_name)
    core.DB_PATH = tmp_path / f"{module_name}.db"
    core.EINGANG = tmp_path / "eingang"
    core.BASE_PATH = tmp_path / "base"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.EINGANG.mkdir(parents=True, exist_ok=True)
    core.BASE_PATH.mkdir(parents=True, exist_ok=True)
    core.PENDING_DIR.mkdir(parents=True, exist_ok=True)
    core.DONE_DIR.mkdir(parents=True, exist_ok=True)
    core.db_init()
    return core


def _insert_version_row(core, *, doc_id: str, file_path: Path, tenant_id: str) -> None:
    con = sqlite3.connect(str(core.DB_PATH))
    try:
        now = "2026-02-10T00:00:00"
        docs_has_tenant = _has_column(con, "docs", "tenant_id")
        versions_has_tenant = _has_column(con, "versions", "tenant_id")

        if docs_has_tenant:
            con.execute(
                """
                INSERT OR IGNORE INTO docs(
                  doc_id, group_key, tenant_id, kdnr, object_folder, doctype, doc_date, created_at
                ) VALUES (?,?,?,?,?,?,?,?)
                """,
                (doc_id, "grp", tenant_id, "", "", "", "", now),
            )
        else:
            con.execute(
                """
                INSERT OR IGNORE INTO docs(
                  doc_id, group_key, kdnr, object_folder, doctype, doc_date, created_at
                ) VALUES (?,?,?,?,?,?,?)
                """,
                (doc_id, "grp", "", "", "", "", now),
            )

        if versions_has_tenant:
            con.execute(
                """
                INSERT INTO versions(
                  doc_id, version_no, bytes_sha256, file_name, file_path,
                  extracted_text, used_ocr, note, created_at, tenant_id
                ) VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    doc_id,
                    1,
                    doc_id,
                    file_path.name,
                    str(file_path),
                    "",
                    0,
                    "test",
                    now,
                    tenant_id,
                ),
            )
        else:
            con.execute(
                """
                INSERT INTO versions(
                  doc_id, version_no, bytes_sha256, file_name, file_path,
                  extracted_text, used_ocr, note, created_at
                ) VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (doc_id, 1, doc_id, file_path.name, str(file_path), "", 0, "test", now),
            )
        con.commit()
    finally:
        con.close()


@pytest.mark.parametrize("module_name", CORE_MODULES)
def test_resolve_source_path_uses_latest_version_when_pending_path_is_stale(
    module_name: str, tmp_path: Path
) -> None:
    core = _setup_core(module_name, tmp_path)
    stale_path = core.EINGANG / "stale.pdf"
    stale_path.write_text("old")

    moved_path = core.BASE_PATH / "tenant_a" / "moved.pdf"
    moved_path.parent.mkdir(parents=True, exist_ok=True)
    moved_path.write_text("new")

    stale_path.unlink()
    doc_id = "doc-123"
    pending = {"path": str(stale_path), "doc_id": doc_id, "tenant_id": "tenant_a"}
    _insert_version_row(core, doc_id=doc_id, file_path=moved_path, tenant_id="tenant_a")

    resolved = core.resolve_source_path(
        "tok-123", pending=pending, tenant_id="tenant_a"
    )
    assert resolved == moved_path


@pytest.mark.parametrize("module_name", CORE_MODULES)
def test_resolve_source_path_rejects_non_allowlisted_version_path(
    module_name: str, tmp_path: Path
) -> None:
    core = _setup_core(module_name, tmp_path)
    outside_path = tmp_path / "outside" / "secret.pdf"
    outside_path.parent.mkdir(parents=True, exist_ok=True)
    outside_path.write_text("x")

    doc_id = "doc-999"
    pending = {
        "path": str(core.PENDING_DIR / "missing.pdf"),
        "doc_id": doc_id,
        "tenant_id": "tenant_a",
    }
    _insert_version_row(
        core, doc_id=doc_id, file_path=outside_path, tenant_id="tenant_a"
    )

    resolved = core.resolve_source_path(
        "tok-999", pending=pending, tenant_id="tenant_a"
    )
    assert resolved is None
