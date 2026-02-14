from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import kukanilea_core_v3_fixed as core
from app.knowledge.core import knowledge_policy_update
from app.knowledge.email_source import knowledge_email_ingest_eml


def _init_core(tmp_path: Path) -> None:
    core.DB_PATH = tmp_path / "core.db"
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()


def test_email_ingest_redacts_pii_and_event_payload_is_clean(tmp_path: Path) -> None:
    _init_core(tmp_path)
    knowledge_policy_update(
        "TENANT_A",
        actor_user_id="dev",
        allow_customer_pii=True,
        allow_email=True,
    )

    eml = (
        b"From: Max Muster <max.muster@example.com>\n"
        b"To: Sales <sales@example.org>\n"
        b"Subject: Kontakt max.muster@example.com\n"
        b"\n"
        b"Meine Nummer +49 123 456 7890. Bitte an max.muster@example.com schreiben."
    )
    knowledge_email_ingest_eml("TENANT_A", "dev", eml, "pii.eml")

    con = sqlite3.connect(str(core.DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        src = con.execute(
            "SELECT subject_redacted FROM knowledge_email_sources WHERE tenant_id='TENANT_A' LIMIT 1"
        ).fetchone()
        assert src is not None
        subj = str(src["subject_redacted"] or "")
        assert "max.muster@example.com" not in subj
        assert "[redacted-email]" in subj or subj == "(no subject)"

        chunk = con.execute(
            "SELECT body FROM knowledge_chunks WHERE tenant_id='TENANT_A' AND source_type='email' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        assert chunk is not None
        body = str(chunk["body"] or "")
        assert "max.muster@example.com" not in body
        assert "+49 123 456 7890" not in body
        assert "[redacted-email]" in body
        assert "[redacted-phone]" in body

        evt = con.execute(
            "SELECT payload_json FROM events WHERE event_type='knowledge_email_ingested' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        assert evt is not None
        payload = str(evt["payload_json"])
        assert "max.muster@example.com" not in payload
        assert not re.search(r"\+?\d[\d\s().-]{6,}\d", payload)
    finally:
        con.close()
