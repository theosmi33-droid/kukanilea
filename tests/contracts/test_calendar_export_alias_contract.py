from __future__ import annotations

from pathlib import Path


def test_calendar_export_alias_returns_ics_without_path_metadata(auth_client, tmp_path, monkeypatch):
    feed = tmp_path / "calendar.ics"
    feed.write_bytes(
        b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//KUKANILEA//EN\r\nEND:VCALENDAR\r\n"
    )

    monkeypatch.setattr(
        "app.knowledge.ics_source.knowledge_ics_build_local_feed",
        lambda tenant_id, **_kwargs: {
            "tenant_id": tenant_id,
            "event_count": 1,
            "feed_path": str(feed),
            "feed_filename": feed.name,
        },
    )

    response = auth_client.get("/calendar/export.ics")
    assert response.status_code == 200
    assert response.headers.get("Content-Type", "").startswith("text/calendar")
    assert response.headers.get("Content-Disposition") == "attachment; filename=calendar.ics"

    body = response.get_data()
    assert body.startswith(b"BEGIN:VCALENDAR")
    assert b"feed_path" not in body
    assert b"feed_filename" not in body


def test_calendar_template_links_to_calendar_blueprint_export() -> None:
    template = Path("/Users/gensuminguyen/Kukanilea/app/templates/calendar.html")
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
