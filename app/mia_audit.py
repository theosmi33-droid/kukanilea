from __future__ import annotations

import json
from typing import Any

from app.event_id_map import entity_id_int
from app.eventlog.core import event_append

MIA_EVENT_PROPOSAL_CREATED = "mia.proposal.created"
MIA_EVENT_CONFIRM_REQUESTED = "mia.confirm.requested"
MIA_EVENT_CONFIRM_GRANTED = "mia.confirm.granted"
MIA_EVENT_CONFIRM_DENIED = "mia.confirm.denied"
MIA_EVENT_CONFIRM_EXPIRED = "mia.confirm.expired"
MIA_EVENT_EXECUTION_STARTED = "mia.execution.started"
MIA_EVENT_EXECUTION_FINISHED = "mia.execution.finished"
MIA_EVENT_EXECUTION_FAILED = "mia.execution.failed"
MIA_EVENT_AUDIT_TRAIL_LINKED = "mia.audit_trail.linked"

MIA_EVENTS_STABLE = {
    MIA_EVENT_PROPOSAL_CREATED,
    MIA_EVENT_CONFIRM_REQUESTED,
    MIA_EVENT_CONFIRM_GRANTED,
    MIA_EVENT_CONFIRM_DENIED,
    MIA_EVENT_CONFIRM_EXPIRED,
    MIA_EVENT_EXECUTION_STARTED,
    MIA_EVENT_EXECUTION_FINISHED,
    MIA_EVENT_EXECUTION_FAILED,
    MIA_EVENT_AUDIT_TRAIL_LINKED,
}

_SECRET_KEYS = {"password", "secret", "token", "api_key", "authorization", "cookie"}


def sanitize_meta(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if key_text.lower() in _SECRET_KEYS:
                out[key_text] = "[REDACTED]"
            else:
                out[key_text] = sanitize_meta(item)
        return out
    if isinstance(value, list):
        return [sanitize_meta(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def stable_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    return sanitize_meta(payload or {})


def emit_mia_event(
    *,
    event_type: str,
    entity_type: str,
    entity_ref: str,
    tenant_id: str,
    payload: dict[str, Any] | None = None,
) -> int:
    if event_type not in MIA_EVENTS_STABLE:
        raise ValueError("invalid_mia_event")
    return event_append(
        event_type=event_type,
        entity_type=str(entity_type or "mia_flow"),
        entity_id=entity_id_int(str(entity_ref or "unknown")),
        payload=stable_payload({"tenant_id": str(tenant_id or ""), **(payload or {})}),
    )


def payload_json(payload: dict[str, Any]) -> str:
    return json.dumps(stable_payload(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
