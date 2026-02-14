from __future__ import annotations

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


def _enable_policy() -> None:
    knowledge_policy_update(
        "TENANT_A",
        actor_user_id="dev",
        allow_customer_pii=True,
        allow_email=True,
    )


def test_ingest_dedup_single_source_and_single_event(tmp_path: Path) -> None:
    _init_core(tmp_path)
    _enable_policy()
    eml = (
        b"From: max@example.com\n"
        b"To: team@example.org\n"
        b"Subject: Angebot\n"
        b"Date: Tue, 14 Feb 2026 10:00:00 +0000\n"
        b"\n"
        b"Bitte ruft mich zur Dachreparatur unter +49 123 456 7890 an."
    )

    r1 = knowledge_email_ingest_eml("TENANT_A", "dev", eml, "x.eml")
    r2 = knowledge_email_ingest_eml("TENANT_A", "dev", eml, "x.eml")
    assert r1["dedup"] is False
    assert r2["dedup"] is True

    con = sqlite3.connect(str(core.DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        src_n = con.execute(
            "SELECT COUNT(*) AS n FROM knowledge_email_sources WHERE tenant_id='TENANT_A'"
        ).fetchone()["n"]
        assert int(src_n) == 1
        chunk_n = con.execute(
            "SELECT COUNT(*) AS n FROM knowledge_chunks WHERE tenant_id='TENANT_A' AND source_type='email'"
        ).fetchone()["n"]
        assert int(chunk_n) >= 1
        ev_n = con.execute(
            "SELECT COUNT(*) AS n FROM events WHERE event_type='knowledge_email_ingested'"
        ).fetchone()["n"]
        assert int(ev_n) == 1
    finally:
        con.close()
