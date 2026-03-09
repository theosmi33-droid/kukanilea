from __future__ import annotations

from app.modules.kalender.calendar_store import CalendarStore
from app.tools.calendar_tools import CalendarCreateEventTool, CalendarFindFreeSlotTool


def test_find_free_slot_is_deterministic(tmp_path):
    store = CalendarStore(db_path=tmp_path / "calendar.sqlite3")
    tenant = "KUKANILEA"
    store.create_event(
        tenant_id=tenant,
        title="Block A",
        start_at="2026-04-03T09:00:00Z",
        end_at="2026-04-03T09:30:00Z",
    )
    store.create_event(
        tenant_id=tenant,
        title="Block B",
        start_at="2026-04-03T10:00:00Z",
        end_at="2026-04-03T10:45:00Z",
    )

    ics_text = (
        "BEGIN:VCALENDAR\r\n"
        "BEGIN:VEVENT\r\n"
        "UID:ics-1\r\n"
        "DTSTART:20260403T093000Z\r\n"
        "DTEND:20260403T100000Z\r\n"
        "SUMMARY:Extern\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )

    first = store.find_free_slot(
        tenant_id=tenant,
        window_start="2026-04-03T09:00:00Z",
        window_end="2026-04-03T12:00:00Z",
        duration_minutes=30,
        granularity_minutes=15,
        ics_texts=[ics_text],
    )
    second = store.find_free_slot(
        tenant_id=tenant,
        window_start="2026-04-03T09:00:00Z",
        window_end="2026-04-03T12:00:00Z",
        duration_minutes=30,
        granularity_minutes=15,
        ics_texts=[ics_text],
    )

    assert first == second
    assert first["status"] == "ok"
    assert first["start_at"] == "2026-04-03T10:45:00Z"
    assert first["end_at"] == "2026-04-03T11:15:00Z"


def test_create_event_emits_audit_event(tmp_path, monkeypatch):
    db_path = tmp_path / "calendar.sqlite3"

    class _Store(CalendarStore):
        def __init__(self):
            super().__init__(db_path=db_path)

    monkeypatch.setattr("app.tools.calendar_tools.CalendarStore", _Store)
    monkeypatch.setattr("app.tools.calendar_tools.get_tenant_id", lambda: "KUKANILEA")
    tool = CalendarCreateEventTool()

    pending = tool.run(
        tenant_id="KUKANILEA",
        title="Kickoff",
        start_at="2026-05-01T08:00:00Z",
        end_at="2026-05-01T09:00:00Z",
        confirm=False,
    )
    assert pending["status"] == "pending_confirmation"

    created = tool.run(
        tenant_id="KUKANILEA",
        title="Kickoff",
        start_at="2026-05-01T08:00:00Z",
        end_at="2026-05-01T09:00:00Z",
        confirm=True,
        created_by="tester",
    )

    assert created["status"] == "created"
    assert created["audit_event"] == "calendar.create_event"

    store = CalendarStore(db_path=db_path)
    audits = store.list_audit("KUKANILEA")
    assert len(audits) == 1
    assert audits[0]["action"] == "calendar.create_event"
    assert audits[0]["payload"]["created_by"] == "tester"


def test_calendar_tool_rejects_mismatched_tenant(monkeypatch):
    monkeypatch.setattr("app.tools.calendar_tools.get_tenant_id", lambda: "KUKANILEA")
    tool = CalendarFindFreeSlotTool()

    try:
        tool.run(
            tenant_id="OTHER",
            window_start="2026-04-03T09:00:00Z",
            window_end="2026-04-03T10:00:00Z",
        )
    except PermissionError as exc:
        assert str(exc) == "tenant_mismatch"
    else:
        raise AssertionError("Expected tenant_mismatch PermissionError")
