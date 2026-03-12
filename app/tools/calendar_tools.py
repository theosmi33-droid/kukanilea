from __future__ import annotations

from typing import Any

from app.modules.kalender.calendar_store import CalendarStore
from app.tools.base_tool import BaseTool
from app.tools.registry import registry
from app.tools.shared_services import get_tenant_id


def _resolve_tenant_id(requested_tenant_id: str | None) -> str | None:
    active_tenant_id = get_tenant_id()
    if not active_tenant_id:
        return None
    if requested_tenant_id and requested_tenant_id != active_tenant_id:
        raise PermissionError("tenant_mismatch")
    return active_tenant_id


def _blocked_tenant_response(*, action: str, requested_tenant_id: str | None) -> dict[str, Any]:
    return {
        "ok": False,
        "status": "blocked",
        "error": "tenant_mismatch",
        "requires_confirm": False,
        "action": action,
        "tenant_id": requested_tenant_id,
    }


class CalendarFindFreeSlotTool(BaseTool):
    name = "calendar.find_free_slot"
    description = "Findet den nächsten freien Kalender-Slot (lokale Events + optionale ICS-Imports)."
    input_schema = {
        "type": "object",
        "properties": {
            "tenant_id": {"type": "string"},
            "window_start": {"type": "string"},
            "window_end": {"type": "string"},
            "duration_minutes": {"type": "integer", "default": 30},
            "granularity_minutes": {"type": "integer", "default": 15},
            "ics_texts": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["tenant_id", "window_start", "window_end"],
    }

    def run(
        self,
        tenant_id: str,
        window_start: str,
        window_end: str,
        duration_minutes: int = 30,
        granularity_minutes: int = 15,
        ics_texts: list[str] | None = None,
    ) -> Any:
        try:
            resolved_tenant_id = _resolve_tenant_id(tenant_id)
        except PermissionError:
            return _blocked_tenant_response(action=self.name, requested_tenant_id=tenant_id)
        if not resolved_tenant_id:
            return {"error": "No tenant context found."}
        store = CalendarStore()
        return store.find_free_slot(
            tenant_id=resolved_tenant_id,
            window_start=window_start,
            window_end=window_end,
            duration_minutes=duration_minutes,
            granularity_minutes=granularity_minutes,
            ics_texts=ics_texts,
        )


class CalendarCreateEventTool(BaseTool):
    name = "calendar.create_event"
    description = "Erstellt einen lokalen Kalendereintrag. Schreibzugriff nur mit expliziter Bestätigung."
    input_schema = {
        "type": "object",
        "properties": {
            "tenant_id": {"type": "string"},
            "title": {"type": "string"},
            "start_at": {"type": "string"},
            "end_at": {"type": "string"},
            "description": {"type": "string"},
            "location": {"type": "string"},
            "created_by": {"type": "string", "default": "system"},
            "confirm": {"type": "boolean", "default": False},
        },
        "required": ["tenant_id", "title", "start_at", "end_at"],
    }

    def run(
        self,
        tenant_id: str,
        title: str,
        start_at: str,
        end_at: str,
        description: str = "",
        location: str = "",
        created_by: str = "system",
        confirm: bool = False,
    ) -> Any:
        try:
            resolved_tenant_id = _resolve_tenant_id(tenant_id)
        except PermissionError:
            return _blocked_tenant_response(action=self.name, requested_tenant_id=tenant_id)
        if not resolved_tenant_id:
            return {"error": "No tenant context found."}
        if not confirm:
            return {
                "status": "pending_confirmation",
                "requires_confirm": True,
                "action": self.name,
                "preview": {
                    "tenant_id": resolved_tenant_id,
                    "title": title,
                    "start_at": start_at,
                    "end_at": end_at,
                    "description": description,
                    "location": location,
                },
            }
        store = CalendarStore()
        event = store.create_event(
            tenant_id=resolved_tenant_id,
            title=title,
            start_at=start_at,
            end_at=end_at,
            description=description,
            location=location,
            created_by=created_by,
        )
        return {"status": "created", "event": event, "audit_event": "calendar.create_event"}


class CalendarUpdateEventTool(BaseTool):
    name = "calendar.update_event"
    description = "Aktualisiert einen lokalen Kalendereintrag. Schreibzugriff nur mit expliziter Bestätigung."
    input_schema = {
        "type": "object",
        "properties": {
            "tenant_id": {"type": "string"},
            "event_id": {"type": "integer"},
            "title": {"type": "string"},
            "start_at": {"type": "string"},
            "end_at": {"type": "string"},
            "description": {"type": "string"},
            "location": {"type": "string"},
            "updated_by": {"type": "string", "default": "system"},
            "confirm": {"type": "boolean", "default": False},
        },
        "required": ["tenant_id", "event_id"],
    }

    def run(
        self,
        tenant_id: str,
        event_id: int,
        title: str | None = None,
        start_at: str | None = None,
        end_at: str | None = None,
        description: str | None = None,
        location: str | None = None,
        updated_by: str = "system",
        confirm: bool = False,
    ) -> Any:
        try:
            resolved_tenant_id = _resolve_tenant_id(tenant_id)
        except PermissionError:
            return _blocked_tenant_response(action=self.name, requested_tenant_id=tenant_id)
        if not resolved_tenant_id:
            return {"error": "No tenant context found."}
        if not confirm:
            return {
                "status": "pending_confirmation",
                "requires_confirm": True,
                "action": self.name,
                "preview": {
                    "tenant_id": resolved_tenant_id,
                    "event_id": event_id,
                    "title": title,
                    "start_at": start_at,
                    "end_at": end_at,
                    "description": description,
                    "location": location,
                },
            }
        store = CalendarStore()
        event = store.update_event(
            tenant_id=resolved_tenant_id,
            event_id=event_id,
            title=title,
            start_at=start_at,
            end_at=end_at,
            description=description,
            location=location,
            updated_by=updated_by,
        )
        return {"status": "updated", "event": event, "audit_event": "calendar.update_event"}


registry.register(CalendarFindFreeSlotTool())
registry.register(CalendarCreateEventTool())
registry.register(CalendarUpdateEventTool())
