from __future__ import annotations

import sqlite3
from pathlib import Path

from flask import Flask

import kukanilea_core_v3_fixed as core
from app.autonomy.source_scan import scan_sources_once, source_watch_config_update
from app.knowledge.core import knowledge_policy_update


def _init_core(tmp_path: Path) -> None:
    core.DB_PATH = tmp_path / "core.db"
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()


def _enable_policies() -> None:
    knowledge_policy_update(
        "TENANT_A",
        actor_user_id="dev",
        allow_customer_pii=True,
        allow_email=True,
        allow_calendar=True,
        allow_documents=True,
    )


def test_source_scan_discovers_and_ingests_eml_and_ics(
    tmp_path: Path, monkeypatch
) -> None:
    _init_core(tmp_path)
    _enable_policies()
    monkeypatch.setenv("KUKANILEA_ANONYMIZATION_KEY", "scan-test-key")

    email_dir = tmp_path / "emails"
    cal_dir = tmp_path / "ics"
    email_dir.mkdir(parents=True, exist_ok=True)
    cal_dir.mkdir(parents=True, exist_ok=True)

    (email_dir / "a.eml").write_bytes(
        b"From: a@example.com\n"
        b"To: b@example.com\n"
        b"Subject: Anfrage\n"
        b"Date: Tue, 14 Feb 2026 10:00:00 +0000\n\n"
        b"Bitte rueckrufen unter +49 170 1234567"
    )
    (cal_dir / "a.ics").write_text(
        "BEGIN:VCALENDAR\n"
        "VERSION:2.0\n"
        "BEGIN:VEVENT\n"
        "DTSTART:20260214T100000Z\n"
        "DTEND:20260214T110000Z\n"
        "SUMMARY:Baustellentermin\n"
        "LOCATION:Lager\n"
        "END:VEVENT\n"
        "END:VCALENDAR\n",
        encoding="utf-8",
    )

    source_watch_config_update(
        "TENANT_A",
        email_inbox_dir=str(email_dir),
        calendar_inbox_dir=str(cal_dir),
        enabled=True,
    )

    result = scan_sources_once("TENANT_A", actor_user_id="dev")
    assert result["ok"] is True
    assert int(result["ingested_ok"]) == 2

    con = sqlite3.connect(str(core.DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        src_files = con.execute(
            "SELECT COUNT(*) AS n FROM source_files WHERE tenant_id='TENANT_A'"
        ).fetchone()["n"]
        assert int(src_files) == 2
        email_n = con.execute(
            "SELECT COUNT(*) AS n FROM knowledge_email_sources WHERE tenant_id='TENANT_A'"
        ).fetchone()["n"]
        assert int(email_n) == 1
        ics_n = con.execute(
            "SELECT COUNT(*) AS n FROM knowledge_ics_sources WHERE tenant_id='TENANT_A'"
        ).fetchone()["n"]
        assert int(ics_n) == 1
    finally:
        con.close()


def test_source_scan_limits_oversize(tmp_path: Path, monkeypatch) -> None:
    _init_core(tmp_path)
    _enable_policies()
    monkeypatch.setenv("KUKANILEA_ANONYMIZATION_KEY", "scan-test-key")

    email_dir = tmp_path / "emails"
    email_dir.mkdir(parents=True, exist_ok=True)
    payload = b"From: a@example.com\nSubject: X\n\n" + (b"A" * 1024)
    (email_dir / "big.eml").write_bytes(payload)

    source_watch_config_update(
        "TENANT_A",
        email_inbox_dir=str(email_dir),
        max_bytes_per_file=128,
    )

    result = scan_sources_once("TENANT_A", actor_user_id="dev")
    assert int(result["skipped_limits"]) == 1
    assert int(result["ingested_ok"]) == 0

    con = sqlite3.connect(str(core.DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            """
            SELECT action, detail_code
            FROM source_ingest_log
            WHERE tenant_id='TENANT_A'
            ORDER BY created_at DESC
            LIMIT 1
            """
        ).fetchone()
        assert row is not None
        assert str(row["action"]) == "skipped_limits"
        assert str(row["detail_code"]) == "oversize"
    finally:
        con.close()


def test_source_scan_read_only_blocks_without_writes(
    tmp_path: Path, monkeypatch
) -> None:
    _init_core(tmp_path)
    monkeypatch.setenv("KUKANILEA_ANONYMIZATION_KEY", "scan-test-key")

    app = Flask(__name__)
    app.config["READ_ONLY"] = True
    with app.app_context():
        result = scan_sources_once("TENANT_A", actor_user_id="dev")
    assert result["reason"] == "read_only"
    assert int(result["skipped_read_only"]) == 1

    con = sqlite3.connect(str(core.DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        cnt = con.execute("SELECT COUNT(*) AS n FROM source_ingest_log").fetchone()["n"]
        assert int(cnt) == 0
    finally:
        con.close()


def test_source_scan_events_are_pii_free(tmp_path: Path, monkeypatch) -> None:
    _init_core(tmp_path)
    _enable_policies()
    monkeypatch.setenv("KUKANILEA_ANONYMIZATION_KEY", "scan-test-key")

    email_dir = tmp_path / "emails"
    email_dir.mkdir(parents=True, exist_ok=True)
    raw_email = (
        b"From: private.person@example.com\n"
        b"To: sales@example.com\n"
        b"Subject: Secret Subject\n"
        b"\n"
        b"Phone +49 170 9999999"
    )
    fp = email_dir / "private.eml"
    fp.write_bytes(raw_email)

    source_watch_config_update("TENANT_A", email_inbox_dir=str(email_dir), enabled=True)
    result = scan_sources_once("TENANT_A", actor_user_id="dev")
    assert int(result["ingested_ok"]) == 1

    con = sqlite3.connect(str(core.DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            "SELECT payload_json FROM events WHERE event_type LIKE 'source_file_%'"
        ).fetchall()
    finally:
        con.close()

    assert rows
    payload_combined = "\n".join(str(r["payload_json"] or "") for r in rows)
    assert str(fp) not in payload_combined
    lower = payload_combined.lower()
    assert "secret subject" not in lower
    assert "private.person@example.com" not in lower
    assert "+49 170" not in lower


def test_source_scan_unchanged_file_is_skipped(tmp_path: Path, monkeypatch) -> None:
    _init_core(tmp_path)
    _enable_policies()
    monkeypatch.setenv("KUKANILEA_ANONYMIZATION_KEY", "scan-test-key")

    email_dir = tmp_path / "emails"
    email_dir.mkdir(parents=True, exist_ok=True)
    (email_dir / "a.eml").write_bytes(
        b"From: a@example.com\nTo: b@example.com\nSubject: Hallo\n\nTest"
    )

    source_watch_config_update("TENANT_A", email_inbox_dir=str(email_dir), enabled=True)

    first = scan_sources_once("TENANT_A", actor_user_id="dev")
    second = scan_sources_once("TENANT_A", actor_user_id="dev")
    assert int(first["ingested_ok"]) == 1
    assert int(second["skipped_unchanged"]) >= 1
