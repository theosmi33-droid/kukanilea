from __future__ import annotations

import sqlite3
from pathlib import Path

from app.demo_data import generate_demo_data


def _prepare_schema(db_path: Path) -> None:
    con = sqlite3.connect(str(db_path))
    try:
        con.executescript(
            """
            CREATE TABLE customers(
              id TEXT PRIMARY KEY,
              tenant_id TEXT,
              name TEXT,
              vat_id TEXT,
              notes TEXT,
              created_at TEXT,
              updated_at TEXT
            );
            CREATE TABLE leads(
              id TEXT PRIMARY KEY,
              tenant_id TEXT,
              status TEXT,
              source TEXT,
              customer_id TEXT,
              contact_name TEXT,
              contact_email TEXT,
              subject TEXT,
              message TEXT,
              created_at TEXT,
              updated_at TEXT
            );
            CREATE TABLE time_projects(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              tenant_id TEXT,
              name TEXT,
              description TEXT,
              status TEXT,
              budget_hours INTEGER,
              budget_cost REAL,
              created_by TEXT,
              created_at TEXT,
              updated_at TEXT
            );
            CREATE TABLE tasks(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              ts TEXT,
              tenant TEXT,
              severity TEXT,
              task_type TEXT,
              status TEXT,
              title TEXT,
              details TEXT,
              meta_json TEXT,
              created_by TEXT
            );
            CREATE TABLE knowledge_chunks(
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
            );
            CREATE TABLE mail_messages(
              id TEXT PRIMARY KEY,
              tenant_id TEXT,
              account_id TEXT,
              uid TEXT,
              message_id TEXT,
              from_redacted TEXT,
              to_redacted TEXT,
              subject_redacted TEXT,
              received_at TEXT,
              body_text_redacted TEXT,
              has_attachments INTEGER,
              created_at TEXT
            );
            """
        )
        con.commit()
    finally:
        con.close()


def test_generate_demo_data_creates_expected_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "core.sqlite3"
    _prepare_schema(db_path)

    summary = generate_demo_data(db_path=db_path, tenant_id="TENANT_X")
    assert summary["customers"] == 3
    assert summary["leads"] == 10
    assert summary["projects"] == 3
    assert summary["tasks"] == 15
    assert summary["knowledge_notes"] == 5
    assert summary["sample_emails"] == 3
