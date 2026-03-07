from __future__ import annotations

import re
from datetime import UTC, datetime

from app.core.event_bus import EventBus, EventType
from app.modules.aufgaben.contracts import create_task
from app.modules.kalender.contracts import create_event
from app.knowledge.ics_source import knowledge_calendar_suggest_from_text


_EMAIL_TODO_PREFIX = re.compile(r"^\s*TODO:\s*(?P<title>.+?)\s*$", re.IGNORECASE)
_FLOWS_REGISTERED = False


def _tenant_from_payload(payload: dict) -> str:
    return str(payload.get("tenant") or "KUKANILEA")


def _create_task_from_email(payload: dict) -> None:
    subject = str(payload.get("subject") or "")
    match = _EMAIL_TODO_PREFIX.match(subject)
    if not match:
        return

    title = match.group("title").strip()
    if not title:
        return

    sender = str(payload.get("from") or payload.get("sender") or "unknown")
    email_id = str(payload.get("email_id") or payload.get("id") or "")
    create_task(
        tenant=_tenant_from_payload(payload),
        title=title,
        details=f"Aus E-Mail von {sender}",
        created_by="eventbus",
        source_ref=f"eventbus:email:{email_id}",
    )


def _normalize_deadline_start(raw_value: str) -> str | None:
    value = str(raw_value or "").strip()
    if not value:
        return None
    if "T" in value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat(timespec="seconds")
        except ValueError:
            return None
    try:
        parsed_date = datetime.fromisoformat(f"{value}T09:00:00+00:00")
    except ValueError:
        return None
    return parsed_date.astimezone(UTC).isoformat(timespec="seconds")


def _create_calendar_event_from_document(payload: dict) -> None:
    tenant = _tenant_from_payload(payload)
    document_name = str(payload.get("filename") or payload.get("document_name") or "Dokument")

    deadline = _normalize_deadline_start(str(payload.get("detected_deadline") or ""))
    if deadline:
        create_event(
            tenant=tenant,
            title=f"Frist aus Dokument: {document_name}",
            starts_at=deadline,
            created_by="eventbus",
        )
        return

    ocr_text = str(payload.get("ocr_text") or "")
    if not ocr_text:
        return

    knowledge_calendar_suggest_from_text(
        tenant,
        "eventbus",
        ocr_text,
        filename_hint=document_name,
        persist=True,
    )


def init_event_flows() -> None:
    global _FLOWS_REGISTERED
    if _FLOWS_REGISTERED:
        return
    EventBus.subscribe(EventType.EMAIL_RECEIVED, _create_task_from_email)
    EventBus.subscribe(EventType.DOCUMENT_PROCESSED, _create_calendar_event_from_document)
    _FLOWS_REGISTERED = True
