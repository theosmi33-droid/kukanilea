from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from flask import Blueprint, current_app, jsonify, render_template, request, session

from app.mail.intake import envelope_from_payload, normalize_intake_payload
from app.auth import login_required, require_role
from app.modules.aufgaben.contracts import create_task
from app.modules.aufgaben.logic import delete_task as aufgaben_delete_task
from app.modules.aufgaben.logic import get_task as aufgaben_get_task
from app.modules.aufgaben.logic import list_tasks as aufgaben_list_tasks
from app.modules.aufgaben.contracts import build_summary as build_aufgaben_summary
from app.modules.aufgaben.logic import update_task as aufgaben_update_task
from app.modules.kalender.contracts import build_health as build_kalender_health
from app.modules.kalender.contracts import build_summary as build_kalender_summary
from app.modules.kalender.contracts import create_invitation
from app.modules.kalender.contracts import create_event
from app.modules.kalender.contracts import update_event
from app.modules.projekte.contracts import create_project
from app.research.service import generate_summary
from app.modules.projects.logic import ProjectManager
from app.mia_audit import (
    MIA_EVENT_AUDIT_TRAIL_LINKED,
    MIA_EVENT_CONFIRM_DENIED,
    MIA_EVENT_CONFIRM_GRANTED,
    MIA_EVENT_CONFIRM_REQUESTED,
    MIA_EVENT_EXECUTION_FAILED,
    MIA_EVENT_EXECUTION_FINISHED,
    MIA_EVENT_EXECUTION_STARTED,
    MIA_EVENT_PROPOSAL_CREATED,
    emit_mia_event,
)

from .rate_limit import search_limiter

bp = Blueprint("api", __name__, url_prefix="/api")


def _tenant() -> str:
    return str(session.get("tenant_id") or current_app.config.get("TENANT_DEFAULT") or "KUKANILEA")


@bp.get("/ping")
@search_limiter.limit_required
def ping():
    return jsonify(ok=True)


@bp.get("/health")
@search_limiter.limit_required
def health():
    auth_db = current_app.extensions["auth_db"]
    core_stats = {}
    profile = None
    is_authenticated = bool(session.get("user"))
    try:
        from app import web  # local import to avoid circular refs

        tenant_id = web.current_tenant()
        core = getattr(web, "core", None)
        if core and callable(getattr(core, "get_health_stats", None)):
            core_stats = core.get_health_stats(tenant_id=tenant_id)
        if is_authenticated and core and callable(getattr(core, "get_profile", None)):
            profile = core.get_profile()
    except Exception:
        core_stats = {}
    payload = dict(
        ok=True,
        schema_version=auth_db.get_schema_version(),
        auth_db_path=str(auth_db.path),
        tenants=auth_db.count_tenants(),
        last_indexed_at=core_stats.get("last_indexed_at"),
        doc_count=core_stats.get("doc_count", 0),
        fts_enabled=core_stats.get("fts_enabled", False),
    )
    if is_authenticated:
        payload["profile"] = profile
    return jsonify(payload)


@bp.get("/kalender/summary")
@search_limiter.limit_required
def kalender_summary():
    tenant = str(session.get("tenant_id") or current_app.config.get("TENANT_DEFAULT") or "KUKANILEA")
    return jsonify(build_kalender_summary(tenant))


@bp.get("/kalender/health")
@search_limiter.limit_required
def kalender_health():
    tenant = _tenant()
    payload, code = build_kalender_health(tenant)
    return jsonify(payload), code


@bp.post("/kalender/events")
@search_limiter.limit_required
def kalender_create_event():
    payload = request.get_json(silent=True) or {}
    tenant = str(session.get("tenant_id") or current_app.config.get("TENANT_DEFAULT") or "KUKANILEA")
    actor = str(session.get("user") or "system")
    title = str(payload.get("title") or "").strip()
    starts_at = str(payload.get("starts_at") or "").strip()
    if not title or not starts_at:
        return jsonify(ok=False, error="title_and_starts_at_required"), 400
    event_payload = create_event(
        tenant=tenant,
        title=title,
        starts_at=starts_at,
        ends_at=str(payload.get("ends_at") or "").strip() or None,
        reminder_minutes=int(payload.get("reminder_minutes") or 0),
        created_by=actor,
    )
    return jsonify(ok=True, event=event_payload), 201


@bp.patch("/kalender/events/<event_id>")
@search_limiter.limit_required
def kalender_update_event(event_id: str):
    payload = request.get_json(silent=True) or {}
    tenant = str(session.get("tenant_id") or current_app.config.get("TENANT_DEFAULT") or "KUKANILEA")
    actor = str(session.get("user") or "system")
    event_payload = update_event(
        tenant=tenant,
        event_id=str(event_id),
        updated_by=actor,
        title=payload.get("title"),
        starts_at=payload.get("starts_at"),
        ends_at=payload.get("ends_at"),
        reminder_minutes=payload.get("reminder_minutes"),
    )
    return jsonify(ok=True, event=event_payload)


@bp.post("/kalender/invitations")
@search_limiter.limit_required
def kalender_create_invitation():
    payload = request.get_json(silent=True) or {}
    tenant = str(session.get("tenant_id") or current_app.config.get("TENANT_DEFAULT") or "KUKANILEA")
    result = create_invitation(
        tenant=tenant,
        title=str(payload.get("title") or "Termin").strip(),
        starts_at=str(payload.get("starts_at") or "").strip(),
        attendees=payload.get("attendees") if isinstance(payload.get("attendees"), list) else [],
        confirm=bool(payload.get("confirm")),
    )
    if result.get("ok") is False:
        return jsonify(result), 409
    return jsonify(result), 202


@bp.get("/aufgaben/summary")
def aufgaben_summary_route():
    return jsonify(build_aufgaben_summary(tenant=_tenant()))


@bp.get("/aufgaben")
def aufgaben_list_route():
    status = request.args.get("status")
    items = aufgaben_list_tasks(tenant=_tenant(), status=status)
    return jsonify(ok=True, items=items)


@bp.post("/aufgaben")
def aufgaben_create_route():
    payload = request.get_json(silent=True) or {}
    created = create_task(
        tenant=_tenant(),
        title=str(payload.get("title") or "Neue Aufgabe"),
        details=str(payload.get("details") or ""),
        due_date=payload.get("due_date"),
        priority=str(payload.get("priority") or "MEDIUM"),
        assigned_to=payload.get("assigned_to"),
        source_type=str(payload.get("source_type") or "doc"),
        source_ref=str(payload.get("source_ref") or ""),
        created_by=str(session.get("user") or "system"),
    )
    task_id = int(created["task_id"])
    task = aufgaben_get_task(tenant=_tenant(), task_id=task_id)
    return jsonify(ok=True, task=task), 201


@bp.get("/aufgaben/<int:task_id>")
def aufgaben_get_route(task_id: int):
    task = aufgaben_get_task(tenant=_tenant(), task_id=task_id)
    if not task:
        return jsonify(ok=False, error="not_found"), 404
    return jsonify(ok=True, task=task)


@bp.put("/aufgaben/<int:task_id>")
@bp.patch("/aufgaben/<int:task_id>")
def aufgaben_update_route(task_id: int):
    payload = request.get_json(silent=True) or {}
    task = aufgaben_update_task(tenant=_tenant(), task_id=task_id, payload=payload)
    if not task:
        return jsonify(ok=False, error="not_found"), 404
    return jsonify(ok=True, task=task)


@bp.delete("/aufgaben/<int:task_id>")
def aufgaben_delete_route(task_id: int):
    deleted = aufgaben_delete_task(tenant=_tenant(), task_id=task_id)
    if not deleted:
        return jsonify(ok=False, error="not_found"), 404
    return jsonify(ok=True)


@bp.post("/intake/normalize")
def intake_normalize():
    payload = request.get_json(silent=True) or {}
    envelope = normalize_intake_payload(payload)
    return jsonify(ok=True, envelope=envelope.to_dict())


@bp.post("/intake/execute")
@login_required
@require_role("OPERATOR")
def intake_execute():
    payload = request.get_json(silent=True) or {}
    envelope_payload = payload.get("envelope") if isinstance(payload.get("envelope"), dict) else {}
    envelope = envelope_from_payload(envelope_payload)

    tenant_id = str(session.get("tenant_id") or current_app.config.get("TENANT_DEFAULT") or "KUKANILEA")
    actor = str(session.get("user") or "system")
    action = envelope.suggested_actions[0] if envelope.suggested_actions else {}
    flow_ref = envelope.thread_id or f"intake-{tenant_id}"
    proposal_event_id = emit_mia_event(
        event_type=MIA_EVENT_PROPOSAL_CREATED,
        entity_type="intake_thread",
        entity_ref=flow_ref,
        tenant_id=tenant_id,
        payload={"actor": actor, "source": envelope.source, "action_type": str(action.get("type") or "create_task")},
    )
    confirm_requested_event_id = emit_mia_event(
        event_type=MIA_EVENT_CONFIRM_REQUESTED,
        entity_type="intake_thread",
        entity_ref=flow_ref,
        tenant_id=tenant_id,
        payload={"actor": actor, "proposal_event_id": proposal_event_id},
    )

    if not bool(payload.get("requires_confirm", True)):
        emit_mia_event(
            event_type=MIA_EVENT_CONFIRM_DENIED,
            entity_type="intake_thread",
            entity_ref=flow_ref,
            tenant_id=tenant_id,
            payload={"actor": actor, "confirm_requested_event_id": confirm_requested_event_id, "reason": "flag_missing"},
        )
        return jsonify(ok=False, error="confirm_required_flag_missing"), 400

    confirm_value = str(payload.get("confirm") or "").strip().lower()
    if confirm_value not in {"yes", "y", "true", "1"}:
        emit_mia_event(
            event_type=MIA_EVENT_CONFIRM_DENIED,
            entity_type="intake_thread",
            entity_ref=flow_ref,
            tenant_id=tenant_id,
            payload={"actor": actor, "confirm_requested_event_id": confirm_requested_event_id, "reason": "explicit_confirm_required"},
        )
        return jsonify(
            ok=False,
            status="blocked",
            error="explicit_confirm_required",
            envelope=envelope.to_dict(),
        ), 409

    confirm_granted_event_id = emit_mia_event(
        event_type=MIA_EVENT_CONFIRM_GRANTED,
        entity_type="intake_thread",
        entity_ref=flow_ref,
        tenant_id=tenant_id,
        payload={"actor": actor, "confirm_requested_event_id": confirm_requested_event_id},
    )
    execution_started_event_id = emit_mia_event(
        event_type=MIA_EVENT_EXECUTION_STARTED,
        entity_type="intake_thread",
        entity_ref=flow_ref,
        tenant_id=tenant_id,
        payload={"actor": actor, "confirm_granted_event_id": confirm_granted_event_id},
    )

    try:
        project_payload = None
        if action.get("project_hint"):
            try:
                project_payload = create_project(
                    tenant=tenant_id,
                    name=str(action.get("project_hint") or "Projekt aus Intake"),
                    description=f"Auto-Vorschlag aus Intake {envelope.thread_id}",
                )
            except Exception as exc:
                current_app.logger.warning("Project creation failed after confirm: %s", exc)
                project_payload = {
                    "status": "proposal_only",
                    "reason": "project_backend_unavailable",
                    "name": str(action.get("project_hint") or "Projekt aus Intake"),
                }

        task_payload = create_task(
            tenant=tenant_id,
            title=str(action.get("title") or envelope.subject or "Neue Anfrage"),
            details="\n".join(envelope.snippets),
            due_date=action.get("due_date"),
            project_hint=action.get("project_hint"),
            calendar_hint=action.get("calendar_hint"),
            created_by=actor,
            source_ref=envelope.thread_id,
        )

        calendar_payload = None
        appointment_action = next(
            (item for item in envelope.suggested_actions if str(item.get("type") or "") == "create_appointment"),
            {},
        )
        starts_at = appointment_action.get("starts_at") or action.get("due_date")
        if starts_at:
            try:
                calendar_payload = create_event(
                    tenant=tenant_id,
                    title=str(
                        appointment_action.get("title")
                        or action.get("calendar_hint")
                        or action.get("title")
                        or "Intake Termin"
                    ),
                    starts_at=str(starts_at),
                    created_by=actor,
                )
            except Exception as exc:
                current_app.logger.warning("Appointment creation failed after confirm: %s", exc)
                calendar_payload = {
                    "status": "proposal_only",
                    "reason": "calendar_backend_unavailable",
                    "starts_at": str(starts_at),
                    "title": str(appointment_action.get("title") or action.get("title") or "Intake Termin"),
                }

        diary_payload = None
        defect_payloads: list[dict[str, object]] = []
        diary_data = envelope_payload.get("diary_entry") if isinstance(envelope_payload.get("diary_entry"), dict) else {}
        diary_body = str(diary_data.get("body") or "").strip()
        if diary_body:
            pm = ProjectManager(current_app.extensions["auth_db"])
            diary_payload = pm.create_diary_entry(
                tenant_id=tenant_id,
                source=str(envelope.source or "upload"),
                thread_id=str(envelope.thread_id or ""),
                title=str(diary_data.get("title") or envelope.subject or ""),
                body=diary_body,
                created_by=actor,
                payload=envelope.to_dict(),
            )
            defects_raw = envelope_payload.get("defects") if isinstance(envelope_payload.get("defects"), list) else []
            for item in defects_raw:
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title") or "").strip()
                if not title:
                    continue
                photos = item.get("photos") if isinstance(item.get("photos"), list) else []
                defect_payloads.append(
                    pm.create_defect_item(
                        tenant_id=tenant_id,
                        diary_entry_id=str(diary_payload.get("id") or "") or None,
                        source=str(envelope.source or "upload"),
                        title=title,
                        description=str(item.get("description") or ""),
                        status=str(item.get("status") or "OPEN"),
                        photos=[str(photo) for photo in photos],
                        created_by=actor,
                    )
                )
    except Exception as exc:
        emit_mia_event(
            event_type=MIA_EVENT_EXECUTION_FAILED,
            entity_type="intake_thread",
            entity_ref=flow_ref,
            tenant_id=tenant_id,
            payload={"actor": actor, "execution_started_event_id": execution_started_event_id, "error": str(exc)},
        )
        raise

    from app import core
    from app.eventlog import event_append

    core.audit_log(
        actor,
        str(session.get("role") or "SYSTEM"),
        "intake_execute_confirmed",
        target=envelope.thread_id,
        meta={
            "source": envelope.source,
            "task_id": task_payload["task_id"],
            "mia": {
                "proposal_event_id": proposal_event_id,
                "confirm_requested_event_id": confirm_requested_event_id,
                "confirm_granted_event_id": confirm_granted_event_id,
                "execution_started_event_id": execution_started_event_id,
            },
        },
        tenant_id=tenant_id,
    )
    event_id = event_append(
        "intake_execute_confirmed",
        "task",
        int(task_payload["task_id"]),
        {"thread_id": envelope.thread_id, "source": envelope.source, "actor": actor},
    )
    execution_finished_event_id = emit_mia_event(
        event_type=MIA_EVENT_EXECUTION_FINISHED,
        entity_type="intake_thread",
        entity_ref=flow_ref,
        tenant_id=tenant_id,
        payload={"actor": actor, "execution_started_event_id": execution_started_event_id, "task_id": task_payload["task_id"]},
    )
    audit_trail_event_id = emit_mia_event(
        event_type=MIA_EVENT_AUDIT_TRAIL_LINKED,
        entity_type="intake_thread",
        entity_ref=flow_ref,
        tenant_id=tenant_id,
        payload={
            "actor": actor,
            "audit_action": "intake_execute_confirmed",
            "audit_target": envelope.thread_id,
            "event_log_id": event_id,
            "execution_finished_event_id": execution_finished_event_id,
        },
    )

    return jsonify(
        ok=True,
        status="executed",
        task=task_payload,
        project=project_payload,
        calendar=calendar_payload,
        diary=diary_payload,
        defects=defect_payloads,
        audit_logged=True,
        event_log_id=event_id,
        mia_event_ids={
            "proposal_created": proposal_event_id,
            "confirm_requested": confirm_requested_event_id,
            "confirm_granted": confirm_granted_event_id,
            "execution_started": execution_started_event_id,
            "execution_finished": execution_finished_event_id,
            "audit_trail_linked": audit_trail_event_id,
        },
    )



@bp.post("/mesh/handshake")
def mesh_handshake():
    """Handles incoming handshake requests from peer Hubs."""
    from flask import request
    from app.core.mesh_network import MeshNetworkManager
    from app.core.mesh_identity import verify_signature, sign_message, ensure_mesh_identity
    import json

    body = request.json
    data = body.get("data")
    sig = body.get("signature")

    if not data or not sig:
        return jsonify(ok=False, error="invalid_request"), 400

    # Verify peer signature
    peer_pub_key = data.get("public_key")
    if not verify_signature(peer_pub_key, json.dumps(data, sort_keys=True).encode('utf-8'), sig):
        return jsonify(ok=False, error="invalid_signature"), 401

    # Register peer locally
    auth_db = current_app.extensions["auth_db"]
    manager = MeshNetworkManager(auth_db)
    manager.register_peer(
        data["node_id"],
        data["name"],
        data["public_key"],
        request.remote_addr
    )

    # Respond with our identity
    my_pub, my_node = ensure_mesh_identity()
    response_data = {
        "node_id": my_node,
        "name": current_app.config.get("APP_NAME", "KUKANILEA Hub"),
        "public_key": my_pub,
        "timestamp": datetime.now(timezone.utc).isoformat() + "Z"
    }
    my_sig = sign_message(json.dumps(response_data, sort_keys=True).encode('utf-8'))

    return jsonify(ok=True, peer=response_data, signature=my_sig)


@bp.get("/outbound/status")
def outbound_status():
    """Returns the current status of the API outbound queue."""
    auth_db = current_app.extensions["auth_db"]
    try:
        with auth_db._db() as con:
            con.row_factory = sqlite3.Row
            rows = con.execute(
                "SELECT status, COUNT(*) as count FROM api_outbound_queue GROUP BY status"
            ).fetchall()
            stats = {row["status"]: row["count"] for row in rows}

            recent_failed = con.execute(
                "SELECT target_system, error_message, last_attempt FROM api_outbound_queue WHERE status = 'failed' ORDER BY last_attempt DESC LIMIT 5"
            ).fetchall()

            payload = {
                "ok": True,
                "stats": stats,
                "recent_failed": [dict(r) for r in recent_failed],
            }
            accept = (request.headers.get("Accept") or "").lower()
            wants_html = (
                "text/html" in accept
                or request.headers.get("HX-Request", "").lower() == "true"
                or (request.args.get("format") or "").lower() == "html"
            )
            if wants_html:
                return render_template("components/outbound_status_panel.html", **payload)
            return jsonify(**payload)
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 500


@bp.post("/research/summary")
def research_summary():
    payload = request.get_json(silent=True) or {}
    query = str(payload.get("query") or "").strip()
    if not query:
        return jsonify(ok=False, error="query_required"), 400

    online = bool(payload.get("online", False))
    confirm = payload.get("confirm")
    result = generate_summary(topic="research", query=query, online=online, confirm=confirm)
    if result["provenance"]["outbound_blocked"]:
        blocked = {**result, "ok": False, "error": "confirm_required"}
        return jsonify(**blocked), 409
    return jsonify(**result)


@bp.post("/news/summary")
def news_summary():
    payload = request.get_json(silent=True) or {}
    query = str(payload.get("query") or "").strip()
    if not query:
        return jsonify(ok=False, error="query_required"), 400

    online = bool(payload.get("online", False))
    confirm = payload.get("confirm")
    result = generate_summary(topic="news", query=query, online=online, confirm=confirm)
    if result["provenance"]["outbound_blocked"]:
        blocked = {**result, "ok": False, "error": "confirm_required"}
        return jsonify(**blocked), 409
    return jsonify(**result)
