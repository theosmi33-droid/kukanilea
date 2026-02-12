from __future__ import annotations

import sqlite3

from app.agents import retrieval_fts


def _seed_core_db(path):
    con = sqlite3.connect(str(path))
    try:
        con.execute(
            "CREATE TABLE tasks(id INTEGER PRIMARY KEY, title TEXT, status TEXT, severity TEXT, details TEXT)"
        )
        con.execute(
            "INSERT INTO tasks(id, title, status, severity, details) VALUES (1,'Rechnung A','OPEN','INFO','Bitte pruefen')"
        )
        con.execute(
            "CREATE TABLE time_projects(id INTEGER PRIMARY KEY, name TEXT, status TEXT)"
        )
        con.execute(
            "INSERT INTO time_projects(id, name, status) VALUES (2,'Baustelle Nord','ACTIVE')"
        )
        con.execute(
            "CREATE TABLE time_entries(id INTEGER PRIMARY KEY, user TEXT, start_at TEXT, duration_seconds INTEGER, note TEXT)"
        )
        con.execute(
            "INSERT INTO time_entries(id, user, start_at, duration_seconds, note) VALUES (3,'dev','2026-01-01T10:00:00',900,'Aufmass')"
        )
        con.commit()
    finally:
        con.close()


def _seed_auth_db(path):
    con = sqlite3.connect(str(path))
    try:
        con.execute(
            "CREATE TABLE users(username TEXT PRIMARY KEY, password_hash TEXT, created_at TEXT)"
        )
        con.execute(
            "INSERT INTO users(username, password_hash, created_at) VALUES ('dev','x','2026-01-01T00:00:00')"
        )
        con.commit()
    finally:
        con.close()


def test_retrieval_schema_queue_and_search(tmp_path, monkeypatch):
    core_db = tmp_path / "core.sqlite3"
    auth_db = tmp_path / "auth.sqlite3"
    _seed_core_db(core_db)
    _seed_auth_db(auth_db)

    monkeypatch.setattr(retrieval_fts.Config, "USER_DATA_ROOT", tmp_path)
    monkeypatch.setattr(retrieval_fts.Config, "CORE_DB", core_db)
    monkeypatch.setattr(retrieval_fts.Config, "AUTH_DB", auth_db)

    retrieval_fts.ensure_schema()
    retrieval_fts.index_all()

    hits = retrieval_fts.search("Rechnung", limit=5)
    assert hits
    assert set(hits[0].keys()) == {"text", "meta", "score"}

    retrieval_fts.enqueue("task", 1, "delete")
    processed = retrieval_fts.process_queue(limit=10)
    assert processed >= 1
    hits_after = retrieval_fts.search("Rechnung", limit=5)
    assert hits_after == []
