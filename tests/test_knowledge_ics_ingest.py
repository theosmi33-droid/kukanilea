from __future__ import annotations

import sqlite3
from pathlib import Path

import kukanilea_core_v3_fixed as core
from app.knowledge.core import knowledge_policy_update, knowledge_search
from app.knowledge.ics_source import knowledge_ics_ingest


def _init_core(tmp_path: Path) -> None:
    core.DB_PATH = tmp_path / "core.db"
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()


def _fixtures_root() -> Path:
    return Path(__file__).resolve().parent / "fixtures" / "ics"


def _read_fixture(name: str) -> bytes:
    return (_fixtures_root() / name).read_bytes()


def _enable_calendar_policy(tenant: str) -> None:
    knowledge_policy_update(
        tenant,
        actor_user_id="dev",
        allow_customer_pii=True,
        allow_calendar=True,
    )


def test_ics_ingest_fixtures_and_unfolding(tmp_path: Path) -> None:
    _init_core(tmp_path)
    _enable_calendar_policy("TENANT_A")

    names = [
        "google_calendar_min.ics",
        "apple_ical_min.ics",
        "outlook_min.ics",
        "malicious_attach.ics",
        "rrule.ics",
    ]
    for name in names:
        out = knowledge_ics_ingest("TENANT_A", "dev", _read_fixture(name), name)
        assert out["source_id"]
        assert out["events_parsed"] >= 1

    con = sqlite3.connect(str(core.DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        src_n = con.execute(
            "SELECT COUNT(*) AS n FROM knowledge_ics_sources WHERE tenant_id='TENANT_A'"
        ).fetchone()["n"]
        assert int(src_n) == 5

        rows = con.execute(
            "SELECT title, body FROM knowledge_chunks WHERE tenant_id='TENANT_A' AND source_type='calendar' ORDER BY id ASC"
        ).fetchall()
        assert rows

        combined = "\n".join(f"{r['title']}\n{r['body']}" for r in rows)
        assert "Google Calendar Summary Part 1 continuation" in combined
        upper = combined.upper()
        assert "ATTACH:" not in upper
        assert "RRULE:" not in upper
    finally:
        con.close()


def test_ics_ingest_respects_max_events_limit(tmp_path: Path) -> None:
    _init_core(tmp_path)
    _enable_calendar_policy("TENANT_A")

    event_tpl = (
        "BEGIN:VEVENT\n"
        "UID:{i}\n"
        "DTSTART:20260214T100000Z\n"
        "DTEND:20260214T110000Z\n"
        "SUMMARY:Event {i}\n"
        "LOCATION:Room {i}\n"
        "END:VEVENT\n"
    )
    body = "".join(event_tpl.format(i=i) for i in range(30))
    ics = ("BEGIN:VCALENDAR\nVERSION:2.0\n" + body + "END:VCALENDAR\n").encode("utf-8")

    out = knowledge_ics_ingest("TENANT_A", "dev", ics, "many.ics")
    assert int(out["events_parsed"]) == 10
    assert int(out["chunks_created"]) <= 10


def test_ics_ingest_tenant_isolation_search(tmp_path: Path) -> None:
    _init_core(tmp_path)
    _enable_calendar_policy("TENANT_A")
    _enable_calendar_policy("TENANT_B")

    data = _read_fixture("google_calendar_min.ics")
    knowledge_ics_ingest("TENANT_A", "dev", data, "google_calendar_min.ics")

    a_hits = knowledge_search(
        "TENANT_A", "Google Calendar Summary", source_type="calendar"
    )
    b_hits = knowledge_search(
        "TENANT_B", "Google Calendar Summary", source_type="calendar"
    )
    assert a_hits
    assert b_hits == []
