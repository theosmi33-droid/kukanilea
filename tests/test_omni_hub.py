from __future__ import annotations

import sqlite3
from pathlib import Path

from flask import Flask

import kukanilea_core_v3_fixed as core
from app.omni.hub import get_event, ingest_fixture, list_events, store_event

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "eml" / "sample_with_pii.eml"


def _init_core(tmp_path: Path) -> None:
    core.DB_PATH = tmp_path / "core.db"
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()


def test_ingest_dry_run_and_commit_dedupe(tmp_path: Path) -> None:
    _init_core(tmp_path)
    dry = ingest_fixture(
        "TENANT_A", channel="email", fixture_path=FIXTURE, dry_run=True
    )
    assert dry["ok"] is True
    assert dry["committed"] is False

    c1 = ingest_fixture(
        "TENANT_A", channel="email", fixture_path=FIXTURE, dry_run=False
    )
    c2 = ingest_fixture(
        "TENANT_A", channel="email", fixture_path=FIXTURE, dry_run=False
    )
    assert c1["ok"] is True
    assert c2["ok"] is True
    assert c1["results"][0]["duplicate"] is False
    assert c2["results"][0]["duplicate"] is True

    con = sqlite3.connect(str(core.DB_PATH))
    try:
        row = con.execute(
            "SELECT COUNT(*) FROM conversation_events WHERE tenant_id='TENANT_A'"
        ).fetchone()
        assert int(row[0]) == 1
    finally:
        con.close()


def test_ingest_redaction_invariant(tmp_path: Path) -> None:
    _init_core(tmp_path)
    ingest_fixture("TENANT_A", channel="email", fixture_path=FIXTURE, dry_run=False)
    con = sqlite3.connect(str(core.DB_PATH))
    try:
        row = con.execute(
            """
            SELECT redacted_payload_json
            FROM conversation_events
            WHERE tenant_id='TENANT_A'
            LIMIT 1
            """
        ).fetchone()
        payload = str(row[0] if row else "")
        assert "qa-test-pii@example.com" not in payload
        assert "+49 151 12345678" not in payload
    finally:
        con.close()


def test_list_get_tenant_isolation(tmp_path: Path) -> None:
    _init_core(tmp_path)
    ingest_fixture("TENANT_A", channel="email", fixture_path=FIXTURE, dry_run=False)
    ingest_fixture("TENANT_B", channel="email", fixture_path=FIXTURE, dry_run=False)

    rows_a = list_events("TENANT_A", channel="email", limit=20)
    rows_b = list_events("TENANT_B", channel="email", limit=20)
    assert len(rows_a) == 1
    assert len(rows_b) == 1
    assert rows_a[0]["tenant_id"] == "TENANT_A"
    assert rows_b[0]["tenant_id"] == "TENANT_B"
    assert get_event("TENANT_B", rows_a[0]["id"]) is None


def test_commit_blocked_in_read_only(tmp_path: Path) -> None:
    _init_core(tmp_path)
    app = Flask(__name__)
    app.config["READ_ONLY"] = True
    with app.app_context():
        try:
            store_event(
                "TENANT_A",
                {
                    "channel": "email",
                    "channel_ref": "<x@example.test>",
                    "direction": "inbound",
                    "occurred_at": "2026-02-16T10:00:00+00:00",
                    "raw_payload": {
                        "from": "a@example.test",
                        "to": "b@example.test",
                        "subject": "S",
                        "body": "B",
                    },
                },
                dry_run=False,
            )
            raise AssertionError("expected read_only")
        except PermissionError as exc:
            assert str(exc) == "read_only"
