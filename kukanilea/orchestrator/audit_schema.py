from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Mapping

CANONICAL_AUDIT_EVENT_TYPES: tuple[str, ...] = (
    "intent_detected",
    "action_selected",
    "confirm_requested",
    "confirm_granted",
    "confirm_denied",
    "confirm_expired",
    "route_blocked",
    "execution_started",
    "execution_succeeded",
    "execution_failed",
)

REQUIRED_AUDIT_FIELDS: tuple[str, ...] = (
    "ts",
    "tenant",
    "user",
    "action",
    "tool",
    "intent",
    "risk",
    "execution_mode",
    "status",
    "reason",
)

_SECRET_TOKENS = (
    "secret",
    "password",
    "token",
    "authorization",
    "cookie",
    "api_key",
    "apikey",
    "session",
)


def sanitize_audit_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        safe: dict[str, Any] = {}
        for key, nested in value.items():
            key_text = str(key).lower()
            if any(marker in key_text for marker in _SECRET_TOKENS):
                safe[str(key)] = "[REDACTED]"
            else:
                safe[str(key)] = sanitize_audit_value(nested)
        return safe
    if isinstance(value, (list, tuple, set)):
        return [sanitize_audit_value(item) for item in value]
    return value


def build_audit_event(
    event_type: str,
    *,
    tenant: str,
    user: str,
    action: str,
    tool: str,
    intent: str,
    risk: str,
    execution_mode: str,
    status: str,
    reason: str,
    meta: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if event_type not in CANONICAL_AUDIT_EVENT_TYPES:
        raise ValueError(f"Unsupported audit event type: {event_type}")

    payload: dict[str, Any] = {
        "event_type": event_type,
        "ts": datetime.now(UTC).isoformat(timespec="seconds"),
        "tenant": str(tenant or "default"),
        "user": str(user or "system"),
        "action": str(action or ""),
        "tool": str(tool or ""),
        "intent": str(intent or "unknown"),
        "risk": str(risk or "unknown"),
        "execution_mode": str(execution_mode or "propose"),
        "status": str(status or "unknown"),
        "reason": str(reason or ""),
    }
    if meta:
        payload["meta"] = sanitize_audit_value(dict(meta))
    return payload


def has_required_audit_fields(payload: Mapping[str, Any]) -> bool:
    return all(str(payload.get(field, "")).strip() for field in REQUIRED_AUDIT_FIELDS)
