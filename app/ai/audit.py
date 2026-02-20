from __future__ import annotations

import uuid
from typing import Any

from app.event_id_map import entity_id_int
from app.eventlog.core import event_append


def _redact_value(value: Any, *, key_name: str = "") -> Any:
    key = str(key_name or "").lower()
    if key in {"email", "token", "secret", "password", "api_key", "authorization"}:
        return "[REDACTED]"

    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            out[str(k)] = _redact_value(v, key_name=str(k))
        return out

    if isinstance(value, list):
        return [_redact_value(v, key_name=key_name) for v in value[:20]]

    if isinstance(value, str):
        txt = value.strip()
        if "@" in txt:
            return "[REDACTED_EMAIL]"
        if len(txt) > 300:
            return txt[:300] + "…"
        return txt

    return value


def audit_tool_call(
    *,
    tenant_id: str,
    user_id: str,
    tool_name: str,
    args: dict[str, Any],
    decision: str,
    status: str,
    detail: str = "",
) -> None:
    try:
        event_append(
            event_type="ai_tool_call",
            entity_type="ai_tool",
            entity_id=entity_id_int(str(uuid.uuid4())),
            payload={
                "tenant_id": str(tenant_id or ""),
                "user_id": str(user_id or "system"),
                "tool_name": str(tool_name or ""),
                "decision": str(decision or ""),
                "status": str(status or ""),
                "detail": str(detail or "")[:200],
                "args": _redact_value(args or {}),
            },
        )
    except Exception:
        pass
