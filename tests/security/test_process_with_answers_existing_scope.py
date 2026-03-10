from __future__ import annotations

import sqlite3
from pathlib import Path

from app.core import logic


def _prepare_logic_db(path: Path) -> None:
    con = sqlite3.connect(str(path))
    try:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS docs(
              doc_id TEXT PRIMARY KEY,
              group_key TEXT
            )
            """
        )
        con.commit()
    finally:
        con.close()


def _patch_process_dependencies(monkeypatch, tmp_path: Path, db_path: Path) -> None:
    monkeypatch.setattr(logic, "BASE_PATH", tmp_path / "kunden")
    monkeypatch.setattr(logic, "ZWISCHENABLAGE", tmp_path / "zwischen")
    monkeypatch.setattr(logic, "TENANT_REQUIRE", False)
    monkeypatch.setattr(logic, "_audit_to_file", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(logic, "_extract_text", lambda _path: ("", False))
    monkeypatch.setattr(logic, "index_upsert_document", lambda **_kwargs: None)
    monkeypatch.setattr(logic, "db_upsert_customer", lambda **_kwargs: None)
    monkeypatch.setattr(logic, "vault_store_evidence", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(logic, "_db_has_doc", lambda _doc_id: False)
    monkeypatch.setattr(logic.Path, "home", classmethod(lambda cls: tmp_path))

    def _db():
        con = sqlite3.connect(str(db_path))
        con.row_factory = sqlite3.Row
        return con

    monkeypatch.setattr(logic, "_db", _db)


def test_process_with_answers_rejects_existing_folder_outside_tenant(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "core.sqlite3"
    _prepare_logic_db(db_path)
    _patch_process_dependencies(monkeypatch, tmp_path, db_path)

    src = tmp_path / "invoice-a.txt"
    src.write_text("payload-a", encoding="utf-8")

    outside = tmp_path / "outside-folder"
    outside.mkdir(parents=True, exist_ok=True)

    folder, target, created_new = logic.process_with_answers(
        src,
        {
            "tenant": "TENANT_A",
            "kdnr": "1001",
            "name": "Alice GmbH",
            "addr": "Hauptstrasse 1",
            "plzort": "10115 Berlin",
            "doctype": "RECHNUNG",
            "use_existing": str(outside),
        },
    )

    tenant_root = (logic.BASE_PATH / logic._safe_fs("TENANT_A")).resolve()
    folder.resolve().relative_to(tenant_root)

    assert folder.resolve() != outside.resolve()
    assert created_new is True
    assert target.exists()


def test_process_with_answers_accepts_existing_folder_within_tenant(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "core.sqlite3"
    _prepare_logic_db(db_path)
    _patch_process_dependencies(monkeypatch, tmp_path, db_path)

    tenant_root = logic.BASE_PATH / logic._safe_fs("TENANT_A")
    existing = tenant_root / "existing-customer-folder"
    existing.mkdir(parents=True, exist_ok=True)

    src = tmp_path / "invoice-b.txt"
    src.write_text("payload-b", encoding="utf-8")

    folder, target, created_new = logic.process_with_answers(
        src,
        {
            "tenant": "TENANT_A",
            "kdnr": "1002",
            "name": "Bob GmbH",
            "addr": "Nebenweg 2",
            "plzort": "80331 Muenchen",
            "doctype": "ANGEBOT",
            "use_existing": str(existing),
        },
    )

    assert folder.resolve() == existing.resolve()
    assert created_new is False
    assert target.exists()
    assert target.parent.resolve() == existing.resolve()
