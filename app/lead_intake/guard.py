from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any

from flask import current_app, g, jsonify, render_template, request

import kukanilea_core_v3_fixed as legacy_core
from app.auth import current_tenant, current_user
from app.event_id_map import entity_id_int
from app.eventlog.core import event_append
from app.lead_intake.core import ConflictError, lead_require_claim_or_free
from app.security_ua_hash import ua_hmac_sha256_hex

ALLOWED_ROUTE_KEYS = {
    "leads_status",
    "leads_screen_accept",
    "leads_screen_ignore",
    "leads_priority",
    "leads_assign",
    "leads_note_add",
    "leads_call_log_create",
    "leads_appointment_create",
    "leads_convert",
}


def _is_api_request() -> bool:
    return bool(request.is_json or request.path.startswith("/api/"))


def _is_htmx_request() -> bool:
    return bool(request.headers.get("HX-Request"))


def _read_only_response():
    rid = getattr(g, "request_id", "")
    if _is_api_request():
        return jsonify({"ok": False, "error_code": "read_only", "request_id": rid}), 403
    return (
        render_template(
            "lead_intake/partials/_error.html",
            message="Read-only mode aktiv. Schreibaktionen sind deaktiviert.",
            request_id=rid,
        ),
        403,
    )


def _lead_claimed_response(claimed_by: str, lead_id: str):
    rid = getattr(g, "request_id", "")
    if _is_api_request():
        return (
            jsonify(
                {
                    "ok": False,
                    "error": "lead_claimed",
                    "claimed_by": claimed_by,
                    "lead_id": lead_id,
                    "request_id": rid,
                }
            ),
            403,
        )
    msg = f"Lead ist derzeit von {claimed_by or 'jemand'} geclaimt."
    return (
        render_template(
            "lead_intake/partials/_claim_error.html",
            message=msg,
            request_id=rid,
        ),
        403,
    )


def _extract_lead_id(kwargs: dict[str, Any], lead_id_kw: str) -> str:
    value = kwargs.get(lead_id_kw)
    if value:
        return str(value)
    form_lead = request.form.get("lead_id")
    if form_lead:
        return str(form_lead)
    payload = request.get_json(silent=True) or {}
    if isinstance(payload, dict) and payload.get("lead_id"):
        return str(payload.get("lead_id"))
    return ""


def _emit_collision_event(*, lead_id: str, claimed_by: str, route_key: str) -> None:
    ua_hash = ua_hmac_sha256_hex(str(request.headers.get("User-Agent") or "")) or ""
    try:
        with legacy_core._DB_LOCK:  # type: ignore[attr-defined]
            con = legacy_core._db()  # type: ignore[attr-defined]
            try:
                event_append(
                    event_type="lead_claim_collision",
                    entity_type="lead",
                    entity_id=entity_id_int(lead_id),
                    payload={
                        "schema_version": 1,
                        "source": "lead_intake/guard",
                        "actor_user_id": current_user() or None,
                        "tenant_id": current_tenant(),
                        "data": {
                            "lead_id": lead_id,
                            "claimed_by_user_id": claimed_by,
                            "route_key": route_key,
                            "ua_hash": ua_hash,
                        },
                    },
                    con=con,
                )
                con.commit()
            finally:
                con.close()
    except Exception:
        return


def require_lead_access(route_key: str, lead_id_kw: str = "lead_id"):
    key = str(route_key or "").strip()
    if key not in ALLOWED_ROUTE_KEYS:
        raise ValueError("invalid_route_key")

    def decorator(fn: Callable[..., Any]):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            if bool(current_app.config.get("READ_ONLY", False)):
                return _read_only_response()

            lead_id = _extract_lead_id(kwargs, lead_id_kw)
            if not lead_id:
                if _is_api_request():
                    return (
                        jsonify(
                            {
                                "ok": False,
                                "error": "validation_error",
                                "message": "lead_id fehlt",
                            }
                        ),
                        400,
                    )
                return (
                    render_template(
                        "lead_intake/partials/_claim_error.html",
                        message="Lead-ID fehlt.",
                        request_id=getattr(g, "request_id", ""),
                    ),
                    400,
                )

            try:
                lead_require_claim_or_free(
                    tenant_id=current_tenant(),
                    lead_id=lead_id,
                    actor_user_id=current_user() or None,
                )
            except ConflictError as exc:
                if str(exc) == "lead_claimed":
                    details = (
                        getattr(exc, "details", {}) if hasattr(exc, "details") else {}
                    )
                    claimed_by = str((details or {}).get("claimed_by") or "")
                    _emit_collision_event(
                        lead_id=lead_id,
                        claimed_by=claimed_by,
                        route_key=key,
                    )
                    return _lead_claimed_response(claimed_by, lead_id)
                return _lead_claimed_response("", lead_id)
            except ValueError as exc:
                if str(exc) == "read_only":
                    return _read_only_response()
                if str(exc) == "not_found":
                    if _is_api_request():
                        return jsonify(
                            {"ok": False, "error": "not_found", "lead_id": lead_id}
                        ), 404
                    return (
                        render_template(
                            "lead_intake/partials/_claim_error.html",
                            message="Lead nicht gefunden.",
                            request_id=getattr(g, "request_id", ""),
                        ),
                        404,
                    )
                return (
                    jsonify({"ok": False, "error": "validation_error"}),
                    400,
                )

            return fn(*args, **kwargs)

        wrapped._requires_lead_access = True  # type: ignore[attr-defined]
        wrapped._lead_route_key = key  # type: ignore[attr-defined]
        return wrapped

    return decorator
