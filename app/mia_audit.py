from __future__ import annotations

import json
from typing import Any

from app.event_id_map import entity_id_int
from app.eventlog.core import event_append

MIA_EVENT_PROPOSAL_CREATED = "mia.proposal.created"
MIA_EVENT_INTENT_DETECTED = "mia.intent.detected"
MIA_EVENT_ACTION_SELECTED = "mia.action.selected"
MIA_EVENT_CONFIRM_REQUESTED = "mia.confirm.requested"
MIA_EVENT_CONFIRM_GRANTED = "mia.confirm.granted"
MIA_EVENT_CONFIRM_DENIED = "mia.confirm.denied"
MIA_EVENT_CONFIRM_EXPIRED = "mia.confirm.expired"
MIA_EVENT_ROUTE_BLOCKED = "mia.route.blocked"
MIA_EVENT_ROUTE_EXECUTED = "mia.route.executed"
MIA_EVENT_EXTERNAL_CALL_BLOCKED = "mia.external_call.blocked"
MIA_EVENT_PARAMETER_VALIDATION_FAILED = "mia.parameter_validation.failed"
MIA_EVENT_EXECUTION_STARTED = "mia.execution.started"
MIA_EVENT_EXECUTION_FINISHED = "mia.execution.finished"
MIA_EVENT_EXECUTION_FAILED = "mia.execution.failed"
MIA_EVENT_AUDIT_TRAIL_LINKED = "mia.audit_trail.linked"

MIA_EVENTS_STABLE = {
    MIA_EVENT_PROPOSAL_CREATED,
    MIA_EVENT_INTENT_DETECTED,
    MIA_EVENT_ACTION_SELECTED,
    MIA_EVENT_CONFIRM_REQUESTED,
    MIA_EVENT_CONFIRM_GRANTED,
    MIA_EVENT_CONFIRM_DENIED,
    MIA_EVENT_CONFIRM_EXPIRED,
    MIA_EVENT_ROUTE_BLOCKED,
    MIA_EVENT_ROUTE_EXECUTED,
    MIA_EVENT_EXTERNAL_CALL_BLOCKED,
    MIA_EVENT_PARAMETER_VALIDATION_FAILED,
    MIA_EVENT_EXECUTION_STARTED,
    MIA_EVENT_EXECUTION_FINISHED,
    MIA_EVENT_EXECUTION_FAILED,
    MIA_EVENT_AUDIT_TRAIL_LINKED,
}

MIA_STATUS_ALLOWLIST = {"detected", "selected", "requested", "granted", "denied", "expired", "blocked", "executed", "failed", "started", "finished"}
MIA_RISK_ALLOWLIST = {"none", "low", "medium", "high", "critical"}

_SECRET_KEY_PATTERNS = (
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "authorization",
    "auth",
    "cookie",
    "session",
    "private_key",
    "access_key",
)


def _is_secret_key(key_text: str) -> bool:
    key = str(key_text or "").strip().lower()
    if not key:
        return False
    return any(pattern in key for pattern in _SECRET_KEY_PATTERNS)


def sanitize_meta(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if _is_secret_key(key_text):
                out[key_text] = "[REDACTED]"
            else:
                out[key_text] = sanitize_meta(item)
        return out
    if isinstance(value, (list, tuple)):
        return [sanitize_meta(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def stable_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    return sanitize_meta(payload or {})


def canonical_mia_payload(
    *,
    tenant_id: str,
    user_id: str,
    action: str,
    status: str,
    risk: str,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    status_value = str(status or "").strip().lower() or "detected"
    risk_value = str(risk or "").strip().lower() or "low"
    if status_value not in MIA_STATUS_ALLOWLIST:
        raise ValueError("invalid_mia_status")
    if risk_value not in MIA_RISK_ALLOWLIST:
        raise ValueError("invalid_mia_risk")
    action_value = str(action or "").strip()
    if not action_value:
        raise ValueError("invalid_mia_action")
    return stable_payload(
        {
            "tenant_id": str(tenant_id or ""),
            "user_id": str(user_id or "system"),
            "action": action_value,
            "status": status_value,
            "risk": risk_value,
            "meta": meta or {},
        }
    )


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


def emit_mia_event_safe(
    *,
    event_type: str,
    entity_type: str,
    entity_ref: str,
    tenant_id: str,
    payload: dict[str, Any] | None = None,
) -> int:
    try:
        return emit_mia_event(
            event_type=event_type,
            entity_type=entity_type,
            entity_ref=entity_ref,
            tenant_id=tenant_id,
            payload=payload,
        )
    except Exception:
        return 0


def payload_json(payload: dict[str, Any]) -> str:
    return json.dumps(stable_payload(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
