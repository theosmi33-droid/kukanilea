from __future__ import annotations

from collections import defaultdict
from threading import RLock
from typing import Callable


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
}


class EventBus:
    """Zentraler Event-Bus für Inter-Tool-Kommunikation."""

    _subscribers: dict[str, list[Callable[[dict], None]]] = defaultdict(list)
    _lock = RLock()

    @classmethod
    def subscribe(cls, event_type: str, handler: Callable[[dict], None]) -> None:
        with cls._lock:
            cls._subscribers[event_type].append(handler)

    @classmethod
    def publish(cls, event_type: str, data: dict) -> None:
        with cls._lock:
            handlers = list(cls._subscribers.get(event_type, []))
        for handler in handlers:
            try:
                handler(data)
            except Exception as exc:  # pragma: no cover - defensive logging branch
                print(f"⚠️  Event handler failed: {exc}")

    @classmethod
    def list_events(cls) -> list[str]:
        with cls._lock:
            return list(cls._subscribers.keys())

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            cls._subscribers = defaultdict(list)
