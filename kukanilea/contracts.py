from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ErrorContract:
    code: str
    message: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChatResponseContract:
    ok: bool
    message: str
    suggestions: List[str] = field(default_factory=list)
    results: List[Dict[str, Any]] = field(default_factory=list)
    actions: List[Dict[str, Any]] = field(default_factory=list)
    request_id: Optional[str] = None
    error: Optional[ErrorContract] = None

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "ChatResponseContract":
        error_payload = payload.get("error")
        error = None
        if isinstance(error_payload, dict):
            error = ErrorContract(
                code=str(error_payload.get("code", "")),
                message=str(error_payload.get("message", "")),
                details=dict(error_payload.get("details", {}) or {}),
            )
        return cls(
            ok=bool(payload.get("ok")),
            message=str(payload.get("message", "")),
            suggestions=list(payload.get("suggestions", []) or []),
            results=list(payload.get("results", []) or []),
            actions=list(payload.get("actions", []) or []),
            request_id=payload.get("request_id"),
            error=error,
        )
