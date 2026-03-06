from __future__ import annotations

import sqlite3

from app import core, create_app
from app.core.event_bus import EventBus
from app.knowledge.ics_source import knowledge_calendar_events_list
import app.knowledge.ics_source as ics_source


def _ensure_knowledge_tables(core_db_path: str) -> None:
    con = sqlite3.connect(core_db_path)
    try:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS events(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              ts TEXT NOT NULL,
              event_type TEXT NOT NULL,
              entity_type TEXT NOT NULL,
              entity_id INTEGER NOT NULL,
              payload_json TEXT NOT NULL,
              prev_hash TEXT NOT NULL,
              hash TEXT NOT NULL UNIQUE
            )
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS knowledge_source_policies(
              tenant_id TEXT PRIMARY KEY,
              allow_manual INTEGER,
              allow_tasks INTEGER,
              allow_projects INTEGER,
              allow_documents INTEGER,
              allow_leads INTEGER,
              allow_email INTEGER,
              allow_calendar INTEGER,
              allow_ocr INTEGER,
              allow_customer_pii INTEGER,
              updated_at TEXT
            )
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS knowledge_fts_fallback(
              rowid INTEGER PRIMARY KEY,
              title TEXT,
              body TEXT,
              tags TEXT
            )
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS knowledge_chunks(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              chunk_id TEXT,
              tenant_id TEXT,
              owner_user_id TEXT,
              source_type TEXT,
              source_ref TEXT,
              title TEXT,
              body TEXT,
              tags TEXT,
              content_hash TEXT,
              is_redacted INTEGER,
              created_at TEXT,
              updated_at TEXT
            )
            """
        )
        con.commit()
    finally:
        con.close()


def test_event_bus_email_todo_creates_task(tmp_path, monkeypatch):
    monkeypatch.setenv("KUKANILEA_AUTH_DB", str(tmp_path / "auth.sqlite3"))
    monkeypatch.setenv("KUKANILEA_CORE_DB", str(tmp_path / "core.sqlite3"))

    app = create_app()
    with app.app_context():
        EventBus.publish(
            "email.received",
            {
                "tenant": "KUKANILEA",
                "email_id": "mail-001",
                "subject": "TODO: Rechnung prüfen",
                "from": "kunde@example.com",
            },
        )

        tasks = core.task_list(tenant="KUKANILEA", status="OPEN")

    matching = [task for task in tasks if task.get("title") == "Rechnung prüfen"]
    assert len(matching) == 1
    assert matching[0].get("created_by") == "eventbus"


def test_event_bus_document_processed_with_deadline_creates_calendar_event(tmp_path, monkeypatch):
    monkeypatch.setenv("KUKANILEA_AUTH_DB", str(tmp_path / "auth.sqlite3"))
    monkeypatch.setenv("KUKANILEA_CORE_DB", str(tmp_path / "core.sqlite3"))

    app = create_app()
    app.config["READ_ONLY"] = False
    _ensure_knowledge_tables(str(app.config["CORE_DB"]))

    with app.app_context():
        monkeypatch.setattr(ics_source, "_policy_allows_calendar", lambda *_args, **_kwargs: True)

        EventBus.publish(
            "document.processed",
            {
                "tenant": "KUKANILEA",
                "filename": "angebot.pdf",
                "detected_deadline": "2026-04-15",
                "ocr_text": "Frist: 15.04.2026",
            },
        )

        events = knowledge_calendar_events_list(
            "KUKANILEA",
            include_manual=True,
            include_deadlines=False,
            include_tasks=False,
            kinds=["appointment"],
        )

    assert any(event.get("title") == "Frist aus Dokument: angebot.pdf" for event in events)
