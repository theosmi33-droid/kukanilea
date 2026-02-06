from __future__ import annotations

from typing import Any, Dict
from flask import jsonify, g


def error_envelope(code: str, message: str, *, details: Dict[str, Any] | None = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "ok": False,
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        },
    }
    request_id = getattr(g, "request_id", None)
    if request_id:
        payload["error"]["details"].setdefault("request_id", request_id)
    return payload


def error_payload(code: str, message: str, *, details: Dict[str, Any] | None = None) -> Dict[str, Any]:
    return error_envelope(code, message, details=details)["error"]


def json_error(code: str, message: str, *, status: int = 400, details: Dict[str, Any] | None = None):
    return jsonify(error_envelope(code, message, details=details)), status
