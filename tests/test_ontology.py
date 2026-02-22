from __future__ import annotations

import sqlite3
from pathlib import Path

from app.ontology.registry import OntologyRegistry


def test_ontology_register_get_search(tmp_path: Path, monkeypatch) -> None:
    db = tmp_path / "core.sqlite3"
    reg = OntologyRegistry()
    monkeypatch.setattr(reg, "_db_path", lambda: db)

    con = sqlite3.connect(str(db))
    try:
        con.execute(
            "CREATE TABLE tasks(id INTEGER PRIMARY KEY, title TEXT, details TEXT)"
        )
        con.execute(
            "INSERT INTO tasks(id, title, details) VALUES (1, 'Dachsanierung', 'Angebot erstellen')"
        )
        con.execute(
            "INSERT INTO tasks(id, title, details) VALUES (2, 'Rechnung', 'Abschlussrechnung senden')"
        )
        con.commit()
    finally:
        con.close()

    reg.register_type(
        "task", "tasks", pk_field="id", title_field="title", description_field="details"
    )

    entity = reg.get_entity("task", 1)
    assert entity["title"] == "Dachsanierung"

    results = reg.search_entities("task", "rechnung", limit=10)
    assert results
    assert any("Rechnung" in str(r.get("title") or "") for r in results)


def test_ontology_unknown_type(tmp_path: Path, monkeypatch) -> None:
    db = tmp_path / "core.sqlite3"
    reg = OntologyRegistry()
    monkeypatch.setattr(reg, "_db_path", lambda: db)
    reg.ensure_schema()

    try:
        reg.get_entity("unknown", 1)
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert str(exc) == "unknown_type"
