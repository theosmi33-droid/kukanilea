from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from threading import RLock
from typing import Any, Callable

from app.logging.structured_logger import log_event


EVENTS: dict[str, str] = {
    "task.created": "Aufgabe erstellt",
    "task.completed": "Aufgabe erledigt",
    "task.deleted": "Aufgabe gelöscht",
    "document.uploaded": "Dokument hochgeladen",
    "document.processed": "Dokument verarbeitet (OCR)",
    "email.received": "E-Mail empfangen",
    "email.sent": "E-Mail versendet",
    "calendar.event_created": "Termin erstellt",
    "calendar.reminder": "Termin-Erinnerung",
    "time.timer_started": "Timer gestartet",
    "time.timer_stopped": "Timer gestoppt",
    "project.card_moved": "Karte verschoben",
    "project.milestone_reached": "Meilenstein erreicht",
    "system.backup_complete": "Backup abgeschlossen",
    "system.license_expired": "Lizenz abgelaufen",
    "mia.intent.detected": "MIA Intent erkannt",
    "mia.action.selected": "MIA Aktion ausgewählt",
    "mia.confirm.requested": "MIA Confirm angefragt",
    "mia.confirm.granted": "MIA Confirm erteilt",
    "mia.confirm.denied": "MIA Confirm abgelehnt",
    "mia.confirm.expired": "MIA Confirm abgelaufen",
    "mia.route.blocked": "MIA Route blockiert",
    "mia.route.executed": "MIA Route ausgeführt",
    "mia.external_call.blocked": "MIA externer Call blockiert",
    "mia.parameter_validation.failed": "MIA Parameter-Validierung fehlgeschlagen",
}


class EventType(str, Enum):
    TASK_CREATED = "task.created"
    TASK_COMPLETED = "task.completed"
    TASK_DELETED = "task.deleted"
    DOCUMENT_UPLOADED = "document.uploaded"
    DOCUMENT_PROCESSED = "document.processed"
    EMAIL_RECEIVED = "email.received"
    EMAIL_SENT = "email.sent"
    CALENDAR_EVENT_CREATED = "calendar.event_created"
    CALENDAR_REMINDER = "calendar.reminder"
    TIME_TIMER_STARTED = "time.timer_started"
    TIME_TIMER_STOPPED = "time.timer_stopped"
    PROJECT_CARD_MOVED = "project.card_moved"
    PROJECT_MILESTONE_REACHED = "project.milestone_reached"
    SYSTEM_BACKUP_COMPLETE = "system.backup_complete"
    SYSTEM_LICENSE_EXPIRED = "system.license_expired"
    MIA_INTENT_DETECTED = "mia.intent.detected"
    MIA_ACTION_SELECTED = "mia.action.selected"
    MIA_CONFIRM_REQUESTED = "mia.confirm.requested"
    MIA_CONFIRM_GRANTED = "mia.confirm.granted"
    MIA_CONFIRM_DENIED = "mia.confirm.denied"
    MIA_CONFIRM_EXPIRED = "mia.confirm.expired"
    MIA_ROUTE_BLOCKED = "mia.route.blocked"
    MIA_ROUTE_EXECUTED = "mia.route.executed"
    MIA_EXTERNAL_CALL_BLOCKED = "mia.external_call.blocked"
    MIA_PARAMETER_VALIDATION_FAILED = "mia.parameter_validation.failed"


@dataclass(frozen=True)
class EventAuditEntry:
    occurred_at: str
    event_type: str
    label: str
    subscriber_count: int
    delivered_count: int
    payload: dict[str, Any]
    failed_handlers: list[str]


class EventBus:
    """Zentraler Event-Bus für Inter-Tool-Kommunikation."""

    _subscribers: dict[str, list[Callable[[dict], None]]] = defaultdict(list)
    _audit_trail: list[EventAuditEntry] = []
    _lock = RLock()

    @classmethod
    def subscribe(cls, event_type: str | EventType, handler: Callable[[dict], None]) -> None:
        normalized = cls._normalize_event_type(event_type)
        with cls._lock:
            cls._subscribers[normalized].append(handler)

    @classmethod
    def publish(cls, event_type: str | EventType, data: dict[str, Any]) -> None:
        normalized = cls._normalize_event_type(event_type)
        payload = dict(data or {})
        with cls._lock:
            handlers = list(cls._subscribers.get(normalized, []))
        failed_handlers: list[str] = []
        delivered_count = 0
        for handler in handlers:
            try:
                handler(payload)
                delivered_count += 1
            except Exception as exc:  # pragma: no cover - defensive logging branch
                failed_handlers.append(getattr(handler, "__name__", repr(handler)))
                print(f"⚠️  Event handler failed: {exc}")

        entry = EventAuditEntry(
            occurred_at=datetime.now(UTC).isoformat(timespec="seconds"),
            event_type=normalized,
            label=EVENTS.get(normalized, "Custom event"),
            subscriber_count=len(handlers),
            delivered_count=delivered_count,
            payload=payload,
            failed_handlers=failed_handlers,
        )
        with cls._lock:
            cls._audit_trail.append(entry)
        log_event(
            "eventbus.publish",
            {
                "event_type": entry.event_type,
                "label": entry.label,
                "occurred_at": entry.occurred_at,
                "subscriber_count": entry.subscriber_count,
                "delivered_count": entry.delivered_count,
                "failed_handlers": entry.failed_handlers,
                "payload": entry.payload,
            },
        )

    @classmethod
    def list_events(cls) -> list[str]:
        with cls._lock:
            return list(cls._subscribers.keys())

    @classmethod
    def audit_entries(cls) -> list[EventAuditEntry]:
        with cls._lock:
            return list(cls._audit_trail)

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            cls._subscribers = defaultdict(list)
            cls._audit_trail = []

    @staticmethod
    def _normalize_event_type(event_type: str | EventType) -> str:
        if isinstance(event_type, EventType):
            return event_type.value
        normalized = str(event_type or "").strip()
        if not normalized:
            raise ValueError("event_type_required")
        return normalized
