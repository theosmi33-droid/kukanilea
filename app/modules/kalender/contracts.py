from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
import re

from app import core


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


def build_summary(tenant: str) -> dict:
    reminders_due = getattr(core, "knowledge_calendar_reminders_due", None)
    reminders = reminders_due(tenant) if callable(reminders_due) else []
    return {
        "status": "ok" if callable(reminders_due) else "degraded",
        "timestamp": _timestamp(),
        "metrics": {
            "due_reminders": len(reminders),
            "ics_export": 1,
        },
    }


def build_health(tenant: str) -> tuple[dict, int]:
    payload = build_summary(tenant)
    payload["metrics"] = {
        **payload["metrics"],
        "backend_ready": int(payload["status"] == "ok"),
        "offline_safe": 1,
    }
    code = 200 if payload["status"] in {"ok", "degraded"} else 503
    return payload, code


def _ics_unescape(value: str) -> str:
    return (
        (value or "")
        .replace(r"\n", "\n")
        .replace(r"\N", "\n")
        .replace(r"\;", ";")
        .replace(r"\,", ",")
        .replace(r"\\", "\\")
        .strip()
    )


def _ics_escape(value: str) -> str:
    return (
        (value or "")
        .replace("\\", r"\\")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\n", r"\n")
        .replace(";", r"\;")
        .replace(",", r"\,")
    )


def _ics_fold(line: str, width: int = 72) -> list[str]:
    if len(line) <= width:
        return [line]
    out = [line[:width]]
    rest = line[width:]
    while rest:
        out.append(f" {rest[: width - 1]}")
        rest = rest[width - 1 :]
    return out


def parse_local_ics(raw_ics: str) -> list[dict[str, str]]:
    text = (raw_ics or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    unfolded: list[str] = []
    for line in lines:
        if (line.startswith(" ") or line.startswith("\t")) and unfolded:
            unfolded[-1] = f"{unfolded[-1]}{line[1:]}"
        else:
            unfolded.append(line)

    events: list[dict[str, str]] = []
    current: dict[str, str] = {}
    in_event = False
    for line in unfolded:
        upper = line.strip().upper()
        if upper == "BEGIN:VEVENT":
            current = {}
            in_event = True
            continue
        if upper == "END:VEVENT":
            if in_event and current.get("start_at"):
                events.append(current)
            in_event = False
            current = {}
            continue
        if not in_event or ":" not in line:
            continue

        left, value = line.split(":", 1)
        key = left.split(";", 1)[0].strip().upper()
        if key == "SUMMARY":
            current["title"] = _ics_unescape(value)
        elif key == "DTSTART":
            current["start_at"] = value.strip()
        elif key == "DTEND":
            current["end_at"] = value.strip()
        elif key == "UID":
            current["uid"] = _ics_unescape(value)
        elif key == "DESCRIPTION":
            current["description"] = _ics_unescape(value)
        elif key == "LOCATION":
            current["location"] = _ics_unescape(value)
    return events


def render_local_ics(events: Iterable[dict[str, str]]) -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//KUKANILEA//Calendar Local//DE",
        "CALSCALE:GREGORIAN",
    ]
    now_utc = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    for idx, event in enumerate(events, start=1):
        start_at = str(event.get("start_at") or "").strip()
        if not start_at:
            continue
        end_at = str(event.get("end_at") or start_at).strip()
        uid = str(event.get("uid") or f"local-{idx}@kukanilea").strip()
        title = _ics_escape(str(event.get("title") or "Termin"))

        block = [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{now_utc}",
            f"DTSTART:{start_at}",
            f"DTEND:{end_at}",
            f"SUMMARY:{title}",
        ]
        description = str(event.get("description") or "").strip()
        if description:
            block.append(f"DESCRIPTION:{_ics_escape(description)}")
        location = str(event.get("location") or "").strip()
        if location:
            block.append(f"LOCATION:{_ics_escape(location)}")
        block.append("END:VEVENT")
        for entry in block:
            lines.extend(_ics_fold(entry))
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def build_appointment_proposal(*, lead: str | None, project: str | None, starts_at: str | None) -> dict:
    lead_clean = re.sub(r"\s+", " ", str(lead or "")).strip()
    project_clean = re.sub(r"\s+", " ", str(project or "")).strip()
    if project_clean and lead_clean:
        title = f"{project_clean}: {lead_clean}"
    else:
        title = project_clean or lead_clean or "Termin"
    return {
        "type": "create_appointment",
        "mode": "proposal",
        "title": title[:180],
        "starts_at": str(starts_at or "").strip() or None,
        "requires_confirm": True,
    }



def create_event(
    *,
    tenant: str,
    title: str,
    starts_at: str,
    created_by: str = "system",
) -> dict:
    event = core.knowledge_calendar_event_create(
        tenant,
        created_by,
        title=title,
        start_at=starts_at,
        end_at=starts_at,
        kind="appointment",
    )
    return {"event_id": str(event.get("id") or ""), "title": title, "starts_at": starts_at}
