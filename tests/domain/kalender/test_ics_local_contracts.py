from __future__ import annotations

from app.modules.kalender.contracts import build_appointment_proposal, parse_local_ics, render_local_ics


def test_parse_local_ics_handles_unfolding_and_escaping() -> None:
    raw = (
        "BEGIN:VCALENDAR\r\n"
        "BEGIN:VEVENT\r\n"
        "UID:a-1\r\n"
        "DTSTART:20270401T090000Z\r\n"
        "DTEND:20270401T100000Z\r\n"
        "SUMMARY:Baustelle\\, Team A\r\n"
        "DESCRIPTION:Anfahrt\\nMaterial\r\n"
        "LOCATION:Lager\\; Nord\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )

    events = parse_local_ics(raw)

    assert len(events) == 1
    assert events[0]["uid"] == "a-1"
    assert events[0]["title"] == "Baustelle, Team A"
    assert events[0]["description"] == "Anfahrt\nMaterial"
    assert events[0]["location"] == "Lager; Nord"


def test_render_local_ics_roundtrip_preserves_core_fields() -> None:
    rendered = render_local_ics(
        [
            {
                "uid": "x-1",
                "title": "Projekt Kickoff",
                "start_at": "20270401T090000Z",
                "end_at": "20270401T100000Z",
                "description": "Agenda",
                "location": "Büro",
            }
        ]
    )

    reparsed = parse_local_ics(rendered)

    assert len(reparsed) == 1
    assert reparsed[0]["uid"] == "x-1"
    assert reparsed[0]["title"] == "Projekt Kickoff"
    assert reparsed[0]["start_at"] == "20270401T090000Z"
    assert reparsed[0]["end_at"] == "20270401T100000Z"


def test_appointment_proposal_stays_in_proposal_mode_until_confirm() -> None:
    proposal = build_appointment_proposal(
        lead="Rückruf Kunde",
        project="Dachsanierung Meier",
        starts_at="2030-07-02T08:30:00+00:00",
    )

    assert proposal["type"] == "create_appointment"
    assert proposal["mode"] == "proposal"
    assert proposal["requires_confirm"] is True
    assert proposal["title"].startswith("Dachsanierung Meier")
