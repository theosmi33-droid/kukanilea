from __future__ import annotations

from tests.contracts.conftest import _make_app


def test_calendar_export_returns_ics_payload(monkeypatch, tmp_path):
    from app.routes import calendar as calendar_routes

    app = _make_app(tmp_path, monkeypatch)

    feed_path = tmp_path / "calendar.ics"
    payload = b"BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n"
    feed_path.write_bytes(payload)

    monkeypatch.setattr(calendar_routes, "current_tenant", lambda: "KUKANILEA")
    monkeypatch.setattr(
        calendar_routes,
        "knowledge_ics_build_local_feed",
        lambda tenant_id: {
            "tenant_id": tenant_id,
            "event_count": 0,
            "feed_path": str(feed_path),
            "feed_filename": "calendar.ics",
        },
    )

    with app.test_request_context("/calendar/export.ics"):
        from flask import session

        session["user"] = "admin"
        session["tenant_id"] = "KUKANILEA"
        response = calendar_routes.export_calendar_ics()

    assert response.status_code == 200
    assert response.mimetype == "text/calendar"
    assert response.get_data() == payload
    assert response.headers["Content-Disposition"] == "attachment; filename=calendar.ics"
