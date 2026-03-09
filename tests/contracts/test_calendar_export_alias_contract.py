from __future__ import annotations

from pathlib import Path

# Regression suite for calendar export endpoint wiring and rendering contracts (v2).


def _ics_bytes() -> bytes:
    return b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//KUKANILEA//EN\r\nEND:VCALENDAR\r\n"


def _patch_calendar_feed_builder(monkeypatch, feed_path: Path, *, feed_filename: str | None = None):
    monkeypatch.setattr(
        "app.routes.calendar.knowledge_ics_build_local_feed",
        lambda tenant_id, **_kwargs: {
            "tenant_id": tenant_id,
            "event_count": 1,
            "feed_path": str(feed_path),
            "feed_filename": feed_filename or feed_path.name,
        },
    )


def _call_calendar_export_view(auth_client):
    from app.routes.calendar import export_calendar_ics

    app = auth_client.application
    with app.test_request_context("/calendar/export.ics"):
        from flask import session

        session["user"] = "admin"
        session["role"] = "ADMIN"
        session["tenant_id"] = "KUKANILEA"
        return export_calendar_ics()


def test_calendar_export_view_returns_ics_without_path_metadata(auth_client, tmp_path, monkeypatch):
    feed = tmp_path / "calendar.ics"
    feed.write_bytes(_ics_bytes())
    _patch_calendar_feed_builder(monkeypatch, feed)

    response = _call_calendar_export_view(auth_client)
    assert response.status_code == 200
    assert response.mimetype == "text/calendar"
    assert response.headers.get("Content-Disposition") == "attachment; filename=calendar.ics"

    body = response.get_data()
    assert body.startswith(b"BEGIN:VCALENDAR")
    assert b"feed_path" not in body
    assert b"feed_filename" not in body


def test_calendar_export_view_returns_empty_body_when_feed_file_missing(auth_client, tmp_path, monkeypatch):
    missing = tmp_path / "does-not-exist.ics"
    _patch_calendar_feed_builder(monkeypatch, missing)

    response = _call_calendar_export_view(auth_client)
    assert response.status_code == 200
    assert response.get_data() == b""
    assert response.mimetype == "text/calendar"


def test_calendar_export_view_does_not_reflect_feed_filename(auth_client, tmp_path, monkeypatch):
    feed = tmp_path / "calendar.ics"
    feed.write_bytes(_ics_bytes())
    _patch_calendar_feed_builder(monkeypatch, feed, feed_filename='"evil.ics";foo="bar"')

    response = _call_calendar_export_view(auth_client)
    assert response.status_code == 200
    assert response.headers.get("Content-Disposition") == "attachment; filename=calendar.ics"


def test_calendar_export_view_passes_session_tenant_to_builder(auth_client, tmp_path, monkeypatch):
    feed = tmp_path / "calendar.ics"
    feed.write_bytes(_ics_bytes())
    seen: dict[str, str] = {}

    def _fake_builder(tenant_id, **_kwargs):
        seen["tenant_id"] = str(tenant_id)
        return {
            "tenant_id": tenant_id,
            "event_count": 1,
            "feed_path": str(feed),
            "feed_filename": feed.name,
        }

    monkeypatch.setattr("app.routes.calendar.knowledge_ics_build_local_feed", _fake_builder)

    response = _call_calendar_export_view(auth_client)
    assert response.status_code == 200
    assert seen["tenant_id"] == "KUKANILEA"


def test_calendar_template_links_to_calendar_blueprint_export() -> None:
    template = Path(__file__).resolve().parents[2] / "app/templates/calendar.html"
    content = template.read_text(encoding="utf-8")
    assert "url_for('calendar.export_calendar_ics')" in content
    assert "url_for('web.calendar_export_ics')" not in content


def test_calendar_page_renders_with_export_link(auth_client, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.routes.calendar.knowledge_calendar_events_list",
        lambda _tenant_id: [],
    )
    response = auth_client.get("/calendar")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "/calendar/export.ics" in body
    assert "Kalender & Fristen" in body


def test_calendar_page_renders_empty_state_when_no_events(auth_client, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.routes.calendar.knowledge_calendar_events_list",
        lambda _tenant_id: [],
    )

    response = auth_client.get("/calendar")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Keine Termine gefunden." in body


def test_calendar_page_renders_event_rows(auth_client, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.routes.calendar.knowledge_calendar_events_list",
        lambda _tenant_id: [
            {
                "start_at": "2030-01-10",
                "title": "Abgabe Angebot",
                "source": "deadline",
                "notes": "Kunde A",
            }
        ],
    )

    response = auth_client.get("/calendar")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Abgabe Angebot" in body
    assert "deadline" in body
    assert "Kunde A" in body


def test_calendar_page_survives_event_source_exception(auth_client, monkeypatch) -> None:
    def _boom(_tenant_id):
        raise RuntimeError("calendar-db-unavailable")

    monkeypatch.setattr("app.routes.calendar.knowledge_calendar_events_list", _boom)

    response = auth_client.get("/calendar")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Kalender & Fristen" in body
    assert "Keine Termine gefunden." in body


def test_calendar_page_contains_expected_table_structure(auth_client, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.routes.calendar.knowledge_calendar_events_list",
        lambda _tenant_id: [],
    )

    response = auth_client.get("/calendar")
    assert response.status_code == 200
    body = response.get_data(as_text=True)

    assert "<table" in body
    assert "Datum" in body
    assert "Ereignis" in body
    assert "Typ" in body
    assert "Notizen" in body
    assert "ICS Export" in body


def test_calendar_blueprint_export_view_returns_ics_response(auth_client, tmp_path, monkeypatch):
    feed = tmp_path / "calendar.ics"
    feed.write_bytes(_ics_bytes())
    _patch_calendar_feed_builder(monkeypatch, feed)

    response = _call_calendar_export_view(auth_client)
    assert response.status_code == 200
    assert response.mimetype == "text/calendar"
    assert response.get_data().startswith(b"BEGIN:VCALENDAR")


def test_calendar_blueprint_export_view_returns_empty_when_file_missing(auth_client, tmp_path, monkeypatch):
    missing = tmp_path / "missing.ics"
    _patch_calendar_feed_builder(monkeypatch, missing)

    response = _call_calendar_export_view(auth_client)
    assert response.status_code == 200
    assert response.get_data() == b""
    assert response.mimetype == "text/calendar"


def test_calendar_blueprint_export_view_uses_constant_attachment_filename(auth_client, tmp_path, monkeypatch):
    feed = tmp_path / "calendar.ics"
    feed.write_bytes(_ics_bytes())
    _patch_calendar_feed_builder(monkeypatch, feed, feed_filename="other_name.ics")

    response = _call_calendar_export_view(auth_client)
    assert response.status_code == 200
    assert response.headers.get("Content-Disposition") == "attachment; filename=calendar.ics"
