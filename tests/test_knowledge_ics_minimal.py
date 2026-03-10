from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.knowledge import ics_source
from app.knowledge.ics_source import (
    _extract_deadline_events_from_ocr_text,
    _parse_events,
    _parse_ics_dt,
    knowledge_calendar_event_delete,
    knowledge_calendar_event_update,
)


def test_parse_ics_dt_supports_date_and_datetime() -> None:
    assert _parse_ics_dt("20260301") == "2026-03-01T00:00:00+00:00"
    assert _parse_ics_dt("20260301T091500Z") == "2026-03-01T09:15:00+00:00"
    assert _parse_ics_dt("not-a-date") is None


def test_parse_events_extracts_allowed_fields_only() -> None:
    lines = [
        "BEGIN:VEVENT",
        "DTSTART:20260301T091500Z",
        "DTEND:20260301T101500Z",
        "SUMMARY:  Baustellen-Termin   A ",
        "LOCATION:  Lager  Nord ",
        "DESCRIPTION:should be ignored",
        "END:VEVENT",
    ]

    events = _parse_events(lines)
    assert len(events) == 1
    event = events[0]
    assert event["DTSTART"] == "2026-03-01T09:15:00+00:00"
    assert event["DTEND"] == "2026-03-01T10:15:00+00:00"
    assert event["SUMMARY"] == "Baustellen-Termin A"
    assert event["LOCATION"] == "Lager Nord"
    assert "DESCRIPTION" not in event


def test_extract_deadline_events_from_ocr_text_detects_payment_due() -> None:
    ocr_text = (
        "Rechnungsdatum: 01.02.2026\n"
        "Zahlbar bis 15.02.2026 ohne Abzug.\n"
    )
    events = _extract_deadline_events_from_ocr_text(
        ocr_text,
        filename_hint="rechnung_4711.pdf",
    )

    assert events
    assert events[0]["kind"] == "payment_due"
    assert events[0]["due_date"] == "2026-02-15"
    assert events[0]["source_filename"] == "rechnung_4711.pdf"


def test_read_task_deadlines_prefers_auth_db_in_app_context(tmp_path, monkeypatch) -> None:
    import sqlite3
    from types import SimpleNamespace

    import app.knowledge.ics_source as ics_source

    auth_db_path = tmp_path / "auth.sqlite3"
    core_db_path = tmp_path / "core.sqlite3"

    auth_con = sqlite3.connect(auth_db_path)
    auth_con.row_factory = sqlite3.Row
    auth_con.execute(
        """
        CREATE TABLE team_tasks(
          id TEXT PRIMARY KEY,
          tenant_id TEXT NOT NULL,
          title TEXT NOT NULL,
          description TEXT,
          due_at TEXT,
          assigned_to TEXT,
          status TEXT NOT NULL
        )
        """
    )
    auth_con.execute(
        """
        INSERT INTO team_tasks(id, tenant_id, title, description, due_at, assigned_to, status)
        VALUES (?,?,?,?,?,?,?)
        """,
        (
            "task-1",
            "tenant-a",
            "Frist",
            "Beschreibung",
            (datetime.now(UTC) + timedelta(days=1)).date().isoformat(),
            "user-1",
            "OPEN",
        ),
    )
    auth_con.commit()
    auth_con.close()

    class FakeAuthDB:
        def _db(self):
            con = sqlite3.connect(auth_db_path)
            con.row_factory = sqlite3.Row
            return con

    def fake_core_db():
        con = sqlite3.connect(core_db_path)
        con.row_factory = sqlite3.Row
        return con

    monkeypatch.setattr(ics_source, "has_app_context", lambda: True)
    monkeypatch.setattr(
        ics_source,
        "current_app",
        SimpleNamespace(extensions={"auth_db": FakeAuthDB()}),
    )
    monkeypatch.setattr(ics_source, "_db", fake_core_db)

    rows = ics_source._read_task_deadlines("tenant-a")

    assert len(rows) == 1
    assert rows[0]["id"] == "task-1"


def test_manual_calendar_update_blocked_by_policy(monkeypatch) -> None:
    monkeypatch.setattr(
        ics_source,
        "knowledge_policy_get",
        lambda _tenant_id: {"allow_calendar": 0, "allow_customer_pii": 1},
    )

    try:
        knowledge_calendar_event_update(
            "tenant-a",
            "user-a",
            event_id="evt-1",
            title="blocked",
        )
        assert False, "expected ValueError"
    except ValueError as exc:
        assert str(exc) == "policy_blocked"


def test_manual_calendar_delete_blocked_by_policy(monkeypatch) -> None:
    monkeypatch.setattr(
        ics_source,
        "knowledge_policy_get",
        lambda _tenant_id: {"allow_calendar": 0, "allow_customer_pii": 1},
    )

    try:
        knowledge_calendar_event_delete(
            "tenant-a",
            "user-a",
            event_id="evt-1",
        )
        assert False, "expected ValueError"
    except ValueError as exc:
        assert str(exc) == "policy_blocked"
