from __future__ import annotations

import logging
from typing import Any, Dict

from flask import g, jsonify, render_template, request

logger = logging.getLogger("kukanilea.errors")


def error_envelope(
    code: str, message: str, *, details: Dict[str, Any] | None = None
) -> Dict[str, Any]:
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


def error_payload(
    code: str, message: str, *, details: Dict[str, Any] | None = None
) -> Dict[str, Any]:
    return error_envelope(code, message, details=details)["error"]


def json_error(
    code: str, message: str, *, status: int = 400, details: Dict[str, Any] | None = None
):
    return jsonify(error_envelope(code, message, details=details)), status


def init_app(app):
    """Register global error handlers."""

    @app.errorhandler(403)
    def forbidden(e):
        if request.path.startswith("/api/"):
            return json_error("forbidden", str(e.description), status=403)
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        if request.path.startswith("/api/"):
            return json_error("not_found", "Resource not found.", status=404)
        return render_template("errors/404.html"), 404

    @app.errorhandler(Exception)
    def handle_exception(e):
        """Global exception handler to prevent raw stack traces from reaching the user."""
        # Always log the full exception internally
        logger.exception("Unhandled Exception: %s", e)

        # Determine if it's an API request
        if request.path.startswith("/api/"):
            return json_error("internal_error", "An internal error occurred.", status=500)

        # For UI requests, show a clean error page
        return render_template("errors/500.html"), 500
