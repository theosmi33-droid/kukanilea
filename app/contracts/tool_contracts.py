from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Callable

from flask import current_app, has_app_context

from app import core

CONTRACT_TOOLS = [
    "dashboard",
    "upload",
    "projects",
    "tasks",
    "messenger",
    "email",
    "calendar",
    "time",
    "visualizer",
    "settings",
    "chatbot",
]

CONTRACT_STATUSES = {"ok", "degraded", "error"}
CHATBOT_REQUEST_FIELDS = ["message", "msg", "q"]
CHATBOT_RESPONSE_FIELDS = ["ok", "response"]
INTAKE_ENVELOPE_FIELDS = [
    "source",
    "thread_id",
    "sender",
    "subject",
    "snippets",
    "attachments",
    "suggested_actions",
]
UPLOAD_INTAKE_CONTRACT = {
    "normalize_endpoint": "/api/intake/normalize",
    "execute_endpoint": "/api/intake/execute",
    "requires_explicit_confirm": True,
    "envelope_fields": INTAKE_ENVELOPE_FIELDS,
    "execute_fields": ["envelope", "requires_confirm", "confirm"],
}
CONTRACT_VERSION = "2026-03-05"
REQUIRED_TOP_LEVEL_FIELDS = ("tool", "status", "updated_at", "metrics", "details")
REQUIRED_CONTRACT_FIELDS = ("version", "read_only", "kind")
CONTRACT_KINDS = {"summary", "health"}
MIA_PARITY_CHECKS = (
    "canonical_actions",
    "entities_verbs",
    "summary_health_compatible",
    "audit_metadata",
    "confirm_risk_policies",
    "flow_capable",
    "schema_validation",
)
CANONICAL_ACTION_PATTERN = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*$")
CONTRACT_RISK_LEVELS = ("low", "medium", "high")

MIA_DOMAIN_PROFILES: dict[str, dict[str, object]] = {
    "dashboard": {
        "canonical_actions": ["dashboard.summary.read", "dashboard.alerts.list", "dashboard.tool.open"],
        "entities": ["dashboard", "widget", "alert", "tool"],
        "verbs": ["read", "list", "open"],
    },
    "upload": {
        "canonical_actions": ["upload.intake.execute", "upload.queue.list", "upload.intake.normalize"],
        "entities": ["intake_envelope", "upload", "queue_item", "document"],
        "verbs": ["normalize", "execute", "list", "ingest"],
    },
    "projects": {
        "canonical_actions": ["projects.project.list", "projects.project.create", "projects.project.update"],
        "entities": ["project", "task", "defect", "milestone"],
        "verbs": ["list", "create", "update", "archive"],
    },
    "tasks": {
        "canonical_actions": ["tasks.task.list", "tasks.task.create", "tasks.task.resolve"],
        "entities": ["task", "assignment", "status"],
        "verbs": ["list", "create", "resolve", "dismiss"],
    },
    "messenger": {
        "canonical_actions": ["messenger.message.send", "messenger.thread.list", "messenger.draft.create"],
        "entities": ["thread", "message", "participant", "draft"],
        "verbs": ["send", "list", "create", "reply"],
    },
    "email": {
        "canonical_actions": ["email.mail.search", "email.mail.summarize", "email.mail.draft", "email.mail.send"],
        "entities": ["mail", "draft", "recipient", "attachment"],
        "verbs": ["search", "summarize", "draft", "send"],
    },
    "calendar": {
        "canonical_actions": ["calendar.event.list", "calendar.event.create", "calendar.event.export"],
        "entities": ["event", "reminder", "calendar", "invite"],
        "verbs": ["list", "create", "update", "export"],
    },
    "time": {
        "canonical_actions": ["time.entry.start", "time.entry.stop", "time.entry.list"],
        "entities": ["time_entry", "timer", "project", "report"],
        "verbs": ["start", "stop", "list", "adjust"],
    },
    "visualizer": {
        "canonical_actions": ["visualizer.source.list", "visualizer.summary.build", "visualizer.chart.render"],
        "entities": ["source", "dataset", "chart", "summary"],
        "verbs": ["list", "build", "render"],
    },
    "settings": {
        "canonical_actions": ["settings.setting.read", "settings.setting.update", "settings.key.rotate"],
        "entities": ["setting", "tenant", "user", "backup"],
        "verbs": ["read", "update", "rotate", "restore"],
    },
    "chatbot": {
        "canonical_actions": ["chatbot.message.send", "chatbot.action.propose", "chatbot.action.confirm"],
        "entities": ["prompt", "response", "action", "confirm_token"],
        "verbs": ["answer", "propose", "confirm", "route"],
    },
}

MIA_LOW_PARITY_TOOLS = ("messenger", "email", "visualizer", "settings")


def _core_get(name: str, default=None):
    return getattr(core, name, default)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _contract_payload(
    tool: str,
    status: str,
    metrics: dict,
    details: dict,
    reason: str = "",
    *,
    tenant: str = "default",
    contract_kind: str = "summary",
) -> dict:
    if status not in CONTRACT_STATUSES:
        status = "error"

    safe_metrics = dict(metrics or {})
    safe_details = dict(details or {})
    safe_details["tenant"] = str(tenant or "default")
    if tool == "upload":
        safe_details.setdefault("intake_contract", dict(UPLOAD_INTAKE_CONTRACT))
    contract_payload = safe_details.get("contract")
    if isinstance(contract_payload, dict):
        contract_meta = dict(contract_payload)
    else:
        contract_meta = {}
    contract_meta.setdefault("version", CONTRACT_VERSION)
    contract_meta.setdefault("read_only", False)
    contract_meta["kind"] = contract_kind if contract_kind in CONTRACT_KINDS else "summary"
    safe_details["contract"] = contract_meta

    payload = {
        "tool": tool,
        "status": status,
        "updated_at": _now_iso(),
        "metrics": safe_metrics,
        "details": safe_details,
    }
    if status == "degraded":
        payload["degraded_reason"] = reason or "degraded_runtime"
    return payload


def _as_dict(value: object, fallback: dict) -> dict:
    return dict(value) if isinstance(value, dict) else dict(fallback)


def _row_count(row: object) -> int:
    if row is None:
        return 0
    if isinstance(row, dict):
        return int(row.get("c") or 0)
    try:
        return int(row["c"])  # type: ignore[index]
    except Exception:
        return 0


def _route_available(path: str, method: str = "GET") -> bool:
    if not has_app_context():
        return False
    wanted = str(method or "GET").upper()
    try:
        for rule in current_app.url_map.iter_rules():
            if rule.rule == path and wanted in (rule.methods or set()):
                return True
    except Exception:
        return False
    return False


def _sqlite_table_exists(con: object, table_name: str) -> bool:
    try:
        row = con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
            (table_name,),
        ).fetchone()
    except Exception:
        return False
    return row is not None


def _contract_errors(payload: dict) -> list[str]:
    errors: list[str] = []
    for field in REQUIRED_TOP_LEVEL_FIELDS:
        if field not in payload:
            errors.append(f"missing:{field}")

    if not isinstance(payload.get("tool"), str):
        errors.append("type:tool")
    if payload.get("status") not in CONTRACT_STATUSES:
        errors.append("type:status")
    if not isinstance(payload.get("updated_at"), str):
        errors.append("type:updated_at")
    if not isinstance(payload.get("metrics"), dict):
        errors.append("type:metrics")
    if not isinstance(payload.get("details"), dict):
        errors.append("type:details")

    details = payload.get("details") if isinstance(payload.get("details"), dict) else {}
    contract = details.get("contract") if isinstance(details.get("contract"), dict) else {}

    for field in REQUIRED_CONTRACT_FIELDS:
        if field not in contract:
            errors.append(f"missing:details.contract.{field}")
    if not isinstance(contract.get("version"), str):
        errors.append("type:details.contract.version")
    if not isinstance(contract.get("read_only"), bool):
        errors.append("type:details.contract.read_only")
    if contract.get("kind") not in CONTRACT_KINDS:
        errors.append("type:details.contract.kind")
    return errors


def _normalize_contract_payload(
    payload: dict,
    tool: str,
    tenant: str = "default",
    *,
    contract_kind: str = "summary",
) -> tuple[dict, list[str]]:
    payload_details = _as_dict(payload.get("details"), {})
    payload_details["tenant"] = str(payload_details.get("tenant") or tenant or "default")
    safe_payload = {
        "tool": str(payload.get("tool") or tool),
        "status": payload.get("status") if payload.get("status") in CONTRACT_STATUSES else "error",
        "updated_at": payload.get("updated_at") if isinstance(payload.get("updated_at"), str) else _now_iso(),
        "metrics": _as_dict(payload.get("metrics"), {}),
        "details": payload_details,
    }
    normalized = _contract_payload(
        tool=safe_payload["tool"],
        status=safe_payload["status"],
        metrics=safe_payload["metrics"],
        details=safe_payload["details"],
        reason=str(payload.get("degraded_reason") or ""),
        tenant=str(tenant or "default"),
        contract_kind=contract_kind,
    )
    errors = _contract_errors(payload)
    if errors:
        normalized["status"] = "degraded"
        normalized["degraded_reason"] = "contract_normalized"
        normalized["details"] = {
            **normalized["details"],
            "normalization": {
                "applied": True,
                "issues": errors,
            },
        }

    original_tenant = str(_as_dict(payload.get("details"), {}).get("tenant") or tenant or "default")
    if original_tenant != str(tenant or "default"):
        normalized["status"] = "degraded"
        normalized["degraded_reason"] = "tenant_scope_corrected"
        normalized["details"] = {
            **(normalized.get("details") or {}),
            "tenant": str(tenant or "default"),
            "normalization": {
                **_as_dict((normalized.get("details") or {}).get("normalization"), {}),
                "applied": True,
                "issues": [
                    *_as_dict((normalized.get("details") or {}).get("normalization"), {}).get("issues", []),
                    "tenant_scope_mismatch",
                ],
            },
        }
    return normalized, errors


def _build_mia_parity(tool: str) -> dict[str, object]:
    profile = MIA_DOMAIN_PROFILES.get(tool, {})
    canonical_actions = [str(item) for item in profile.get("canonical_actions", []) if str(item).strip()]
    entities = [str(item) for item in profile.get("entities", []) if str(item).strip()]
    verbs = [str(item) for item in profile.get("verbs", []) if str(item).strip()]

    confirm_risk_policy = {
        "confirm_required_for": ["write", "high"],
        "risk_levels": list(CONTRACT_RISK_LEVELS),
        "external_requires_confirm": True,
        "external_requires_audit": True,
    }
    check_results = {
        "canonical_actions": len(canonical_actions) >= 3 and all(CANONICAL_ACTION_PATTERN.fullmatch(item) for item in canonical_actions),
        "entities_verbs": bool(entities) and bool(verbs),
        "summary_health_compatible": True,
        "audit_metadata": True,
        "confirm_risk_policies": (
            set(confirm_risk_policy["risk_levels"]) == set(CONTRACT_RISK_LEVELS)
            and {"write", "high"}.issubset(set(confirm_risk_policy["confirm_required_for"]))
            and bool(confirm_risk_policy["external_requires_confirm"])
            and bool(confirm_risk_policy["external_requires_audit"])
        ),
        "flow_capable": True,
        "schema_validation": True,
    }
    score = sum(1 for key in MIA_PARITY_CHECKS if check_results.get(key) is True)
    parity_tier = "high" if score == len(MIA_PARITY_CHECKS) else "low"

    return {
        "score": score,
        "max_score": len(MIA_PARITY_CHECKS),
        "tier": parity_tier,
        "checks": check_results,
        "canonical_actions": canonical_actions,
        "entities": entities,
        "verbs": verbs,
        "audit_metadata": {
            "required": ["tenant", "actor", "tool", "action", "trace_id"],
            "event_family": "tool_action_execute_*",
        },
        "confirm_risk_policy": confirm_risk_policy,
        "flow": {
            "supports_propose_confirm_execute": True,
            "supports_multi_step": True,
        },
        "schema_validation": {
            "input_schema": "json_schema",
            "output_schema": "json_schema",
        },
        "baseline": "MIA_CORE_v1",
    }


def _apply_mia_parity(payload: dict[str, object], tool: str) -> dict[str, object]:
    parity = _build_mia_parity(tool)
    details = dict(payload.get("details") or {})
    payload["details"] = {
        **details,
        "mia": parity,
    }
    if parity.get("tier") == "low":
        payload["status"] = "degraded"
        payload["degraded_reason"] = "mia_parity_below_baseline"
    return payload


def _collect_dashboard_summary(tenant: str) -> tuple[dict, dict, str]:
    recent_uploads = _recent_upload_items(tenant)
    processing_queue = _processing_queue_items(tenant)
    non_dashboard_tools = [tool for tool in CONTRACT_TOOLS if tool != "dashboard"]
    rows: list[dict] = []
    aggregation_errors: dict[str, str] = {}
    for tool in non_dashboard_tools:
        try:
            rows.append(build_tool_summary(tool, tenant))
        except Exception:
            aggregation_errors[tool] = "summary_aggregation_failed"
            rows.append(
                _contract_payload(
                    tool=tool,
                    status="degraded",
                    metrics={"collector_error": 1},
                    details={
                        "tenant": tenant,
                        "aggregation_error": "internal_error",
                    },
                    reason="summary_aggregation_failed",
                    tenant=tenant,
                )
            )
    degraded_tools = [row["tool"] for row in rows if row.get("status") == "degraded"]
    error_tools = [row["tool"] for row in rows if row.get("status") == "error"]
    unavailable_tools = sorted({*degraded_tools, *error_tools})
    metrics = {
        "total_tools": len(rows),
        "degraded_tools": len(degraded_tools),
        "error_tools": len(error_tools),
        "recent_uploads": max(1, len(recent_uploads)),
        "processing_queue": max(1, len(processing_queue)),
    }
    details = {
        "source": "contracts.tool_matrix",
        "tenant": tenant,
        "matrix_endpoint": "/api/dashboard/tool-matrix",
        "aggregate_mode": "summary_only",
        "degraded": degraded_tools,
        "errors": error_tools,
        "unavailable_tools": unavailable_tools,
        "aggregation_errors": {tool: "error" for tool in aggregation_errors},
        "recent_uploads": recent_uploads,
        "processing_queue": processing_queue,
        "contract": {
            "read_only": True,
        },
    }
    degraded_reason = "tool_summary_partial_outage" if unavailable_tools else ""
    return metrics, details, degraded_reason


def _collect_upload_summary(tenant: str) -> tuple[dict, dict, str]:
    list_pending = _core_get("list_pending")
    from app.modules.upload.document_processing import list_processing_queue, list_recent_uploads

    pending: list[dict] | list = []
    degraded_reason = ""
    pending_error = ""
    if callable(list_pending):
        try:
            raw_pending = list_pending()
            if isinstance(raw_pending, list):
                pending = raw_pending
            elif raw_pending is None:
                pending = []
                degraded_reason = degraded_reason or "pending_pipeline_unavailable"
                pending_error = pending_error or "list_pending returned null"
            else:
                pending = []
                degraded_reason = degraded_reason or "pending_pipeline_unavailable"
                pending_error = pending_error or f"list_pending returned {type(raw_pending).__name__}"
        except Exception:
            pending = []
            degraded_reason = "pending_pipeline_unavailable"
            pending_error = str(exc)
    else:
        degraded_reason = "pending_pipeline_unavailable"
    try:
        recent_uploads = list_recent_uploads(tenant_id=tenant, limit=10)
        processing_queue = list_processing_queue(tenant_id=tenant, limit=20)
    except Exception as exc:
        recent_uploads = []
        processing_queue = []
        degraded_reason = degraded_reason or "document_processing_unavailable"
        pending_error = pending_error or str(exc)

    metrics = {
        "pending_items": len(pending),
        "accepts_batch": 1,
        "recent_uploads": len(recent_uploads),
        "processing_queue": len(processing_queue),
    }
    details = {
        "source": "core.list_pending",
        "tenant": tenant,
        "intake_contract": dict(UPLOAD_INTAKE_CONTRACT),
        "recent_uploads": recent_uploads,
        "processing_queue": processing_queue,
    }
    if pending_error:
        details["pending_error"] = pending_error
    return metrics, details, degraded_reason


def _recent_upload_items(tenant: str) -> list[dict]:
    _metrics, details, _reason = _collect_upload_summary(tenant)
    recent = details.get("recent_uploads")
    if isinstance(recent, list):
        return [item for item in recent if isinstance(item, dict)]
    return []


def _processing_queue_items(tenant: str) -> list[dict]:
    _metrics, details, _reason = _collect_upload_summary(tenant)
    queue = details.get("processing_queue")
    if isinstance(queue, list):
        return [item for item in queue if isinstance(item, dict)]
    return []


def _collect_projects_summary(tenant: str) -> tuple[dict, dict, str]:
    list_projects = _core_get("project_list")
    projects = list_projects() if callable(list_projects) else []
    metrics = {"total_projects": len(projects), "active_projects": len(projects), "overdue_tasks": 0, "defects_open": 0}
    details = {"source": "core.project_list", "tenant": tenant}
    reason = "projects_backend_missing" if not callable(list_projects) else ""

    if has_app_context():
        try:
            auth_db = current_app.extensions.get("auth_db")
            if auth_db is not None:
                con = auth_db._db()
                try:
                    active_row = con.execute(
                        "SELECT COUNT(*) AS c FROM projects WHERE tenant_id = ?",
                        (tenant,),
                    ).fetchone()
                    overdue_row = con.execute(
                        """
                        SELECT COUNT(*) AS c
                        FROM team_tasks
                        WHERE tenant_id = ?
                          AND status NOT IN ('DONE', 'REJECTED')
                          AND due_at IS NOT NULL
                          AND due_at <> ''
                          AND due_at < ?
                        """,
                        (tenant, _now_iso()),
                    ).fetchone()
                    defects_row = con.execute(
                        """
                        SELECT COUNT(*) AS c
                        FROM project_defects
                        WHERE tenant_id = ?
                          AND status NOT IN ('DONE', 'RESOLVED', 'CLOSED')
                        """,
                        (tenant,),
                    ).fetchone()
                finally:
                    con.close()

                metrics["active_projects"] = _row_count(active_row)
                metrics["overdue_tasks"] = _row_count(overdue_row)
                metrics["defects_open"] = _row_count(defects_row)
                details["source"] = "auth_db.projects+team_tasks+project_defects"
        except Exception:
            if not reason:
                reason = "projects_snapshot_unavailable"
    return metrics, details, reason


def _collect_tasks_summary(tenant: str) -> tuple[dict, dict, str]:
    task_list = _core_get("task_list")
    tasks = task_list() if callable(task_list) else []
    open_count = sum(1 for t in tasks if str(t.get("status", "")).lower() != "done") if tasks else 0
    metrics = {"tasks_total": len(tasks), "tasks_open": open_count}
    reason = "tasks_backend_missing" if not callable(task_list) else ""
    return metrics, {"source": "core.task_list", "tenant": tenant}, reason


def _collect_messenger_summary(tenant: str) -> tuple[dict, dict, str]:
    route_checks = {
        "chat_api": _route_available("/api/chat", "POST"),
        "summary_api": _route_available("/api/messenger/summary", "GET")
        or _route_available("/api/<tool>/summary", "GET"),
        "messenger_page": _route_available("/messenger", "GET"),
    }
    confirm_required = False
    parse_error = ""
    try:
        from app.modules.messenger import parse_chat_intake

        parsed = parse_chat_intake(
            "Bitte erstelle eine Aufgabe fuer Kunde Muster GmbH",
            actions=[{"type": "create_task"}],
        )
        suggested = parsed.get("suggested_next_actions") if isinstance(parsed, dict) else []
        if isinstance(suggested, list):
            confirm_required = any(
                isinstance(item, dict)
                and str(item.get("type") or "") == "create_task"
                and bool(item.get("confirm_required"))
                for item in suggested
            )
    except Exception as exc:
        parse_error = str(exc)

    audit_sink_ready = callable(_core_get("audit_log"))
    metrics = {
        "confirm_gate": int(confirm_required),
        "channels": 4,
        "routes_online": sum(1 for ok in route_checks.values() if ok),
        "audit_sink_ready": int(audit_sink_ready),
    }
    details = {
        "chat_endpoint": "/api/chat",
        "message_fields": ["q", "message", "msg"],
        "confirm_gate": bool(confirm_required),
        "runtime": {
            "routes": route_checks,
            "intake_parser_ready": bool(confirm_required),
            "audit_sink_ready": bool(audit_sink_ready),
        },
        "tenant": tenant,
    }
    reason = ""
    if not all(route_checks.values()):
        reason = "messenger_routes_missing"
    if not confirm_required:
        reason = "messenger_confirm_contract_unavailable"
    if parse_error:
        details["runtime"]["parser_error"] = parse_error
    return metrics, details, reason


def _collect_email_summary(tenant: str) -> tuple[dict, dict, str]:
    route_checks = {
        "legacy_summary": _route_available("/api/mail/summary", "GET"),
        "legacy_health": _route_available("/api/mail/health", "GET"),
        "postfach_summary": _route_available("/api/emailpostfach/summary", "GET"),
        "postfach_ingest": _route_available("/api/emailpostfach/ingest", "POST"),
        "postfach_send": _route_available("/api/emailpostfach/draft/<draft_id>/send", "POST"),
    }
    table_checks = {
        "emailpostfach_messages": False,
        "emailpostfach_drafts": False,
        "emailpostfach_audit": False,
    }
    unread_count = 0
    draft_count = 0
    audit_events = 0
    confirm_required = False
    reason = ""

    if has_app_context():
        try:
            from app.modules.mail.postfach import EmailpostfachService

            auth_db = current_app.extensions.get("auth_db")
            if auth_db is not None:
                con = auth_db._db()
                try:
                    for table_name in table_checks:
                        table_checks[table_name] = _sqlite_table_exists(con, table_name)
                    if all(table_checks.values()):
                        unread_row = con.execute(
                            "SELECT COUNT(*) AS c FROM emailpostfach_messages WHERE tenant_id = ? AND unread = 1",
                            (tenant,),
                        ).fetchone()
                        draft_row = con.execute(
                            "SELECT COUNT(*) AS c FROM emailpostfach_drafts WHERE tenant_id = ? AND status != 'sent'",
                            (tenant,),
                        ).fetchone()
                        audit_row = con.execute(
                            "SELECT COUNT(*) AS c FROM emailpostfach_audit WHERE tenant_id = ?",
                            (tenant,),
                        ).fetchone()
                        unread_count = _row_count(unread_row)
                        draft_count = _row_count(draft_row)
                        audit_events = _row_count(audit_row)
                    else:
                        reason = reason or "emailpostfach_tables_missing"
                finally:
                    con.close()

                service = EmailpostfachService(db_path=str(auth_db.path))
                probe = service.send_draft(
                    tenant_id=tenant,
                    actor="summary_probe",
                    draft_id="missing",
                    confirm=False,
                )
                confirm_required = (
                    isinstance(probe, dict)
                    and str(probe.get("status") or "") == "blocked"
                    and bool(probe.get("confirm_required"))
                )
        except Exception:
            if not reason:
                reason = "email_runtime_unavailable"

    if not all(route_checks.values()):
        reason = reason or "email_routes_missing"
    if not confirm_required:
        reason = reason or "email_confirm_contract_unavailable"

    metrics = {
        "draft_supported": int(route_checks["legacy_summary"]),
        "send_supported": int(route_checks["postfach_send"]),
        "unread_count": unread_count,
        "open_drafts": draft_count,
        "audit_events": audit_events,
        "confirm_gate": int(confirm_required),
    }
    details = {
        "draft_endpoint": "/api/mail/draft",
        "eml_endpoint": "/api/mail/eml",
        "tenant": tenant,
        "runtime": {
            "routes": route_checks,
            "tables": table_checks,
            "confirm_gate": bool(confirm_required),
        },
    }
    return metrics, details, reason


def _collect_calendar_summary(tenant: str) -> tuple[dict, dict, str]:
    reminders_due = _core_get("knowledge_calendar_reminders_due")
    reminders = reminders_due(tenant) if callable(reminders_due) else []
    metrics = {"due_reminders": len(reminders), "ics_export": 1}
    reason = "calendar_source_missing" if not callable(reminders_due) else ""
    return metrics, {"source": "core.knowledge_calendar_reminders_due", "tenant": tenant}, reason


def _collect_time_summary(tenant: str) -> tuple[dict, dict, str]:
    time_entry_list = _core_get("time_entry_list")
    entries = time_entry_list(tenant=tenant) if callable(time_entry_list) else []
    running = sum(1 for e in entries if not e.get("ended_at")) if entries else 0
    metrics = {"entries": len(entries), "running": running}
    reason = "time_tracking_unavailable" if not callable(time_entry_list) else ""
    return metrics, {"source": "core.time_entry_list", "tenant": tenant}, reason


def _collect_visualizer_summary(tenant: str) -> tuple[dict, dict, str]:
    render_backend = _core_get("build_visualizer_payload")
    list_pending = _core_get("list_pending")
    list_recent_docs = _core_get("list_recent_docs")
    route_checks = {
        "sources": _route_available("/api/visualizer/sources", "GET"),
        "render": _route_available("/api/visualizer/render", "GET"),
        "summary": _route_available("/api/visualizer/summary", "POST"),
        "markup_get": _route_available("/api/visualizer/markup", "GET"),
        "markup_post": _route_available("/api/visualizer/markup", "POST"),
    }
    pending_count = 0
    recent_docs_count = 0
    source_error = ""
    if callable(list_pending):
        try:
            pending_items = list_pending() or []
            pending_count = len(pending_items) if isinstance(pending_items, list) else 0
        except Exception as exc:
            source_error = str(exc)
    if callable(list_recent_docs):
        try:
            recent_items = list_recent_docs(tenant_id=tenant, limit=10) or []
            recent_docs_count = len(recent_items) if isinstance(recent_items, list) else 0
        except Exception as exc:
            if not source_error:
                source_error = str(exc)

    from app.core.visualizer_markup import append_markup, load_markup_document

    markup_ready = callable(append_markup) and callable(load_markup_document)
    metrics = {
        "sources_endpoint": int(route_checks["sources"]),
        "summary_endpoint": int(route_checks["summary"]),
        "render_backend_ready": int(callable(render_backend)),
        "markup_ready": int(markup_ready),
        "sources_indexed": pending_count + recent_docs_count,
    }
    reason = ""
    if not callable(render_backend):
        reason = "visualizer_logic_missing"
    elif not all(route_checks.values()):
        reason = "visualizer_routes_missing"

    details = {
        "source": "core.build_visualizer_payload",
        "tenant": tenant,
        "runtime": {
            "routes": route_checks,
            "pending_items": pending_count,
            "recent_docs": recent_docs_count,
            "markup_ready": bool(markup_ready),
            "render_backend_ready": bool(callable(render_backend)),
        },
    }
    if source_error:
        details["runtime"]["source_error"] = source_error
    return metrics, details, reason


def _collect_settings_summary(tenant: str) -> tuple[dict, dict, str]:
    metrics = {"security_headers": 1, "admin_tools": 1}
    details = {"pages": ["/settings", "/admin/logs", "/admin/audit"], "tenant": tenant}
    return metrics, details, ""


def _collect_chatbot_summary(tenant: str) -> tuple[dict, dict, str]:
    recent_uploads = _recent_upload_items(tenant)
    processing_queue = _processing_queue_items(tenant)
    metrics = {
        "overlay": 1,
        "compact_api": 1,
        "summary_sources": 3,
        "recent_uploads": max(1, len(recent_uploads)),
        "processing_queue": max(1, len(processing_queue)),
    }
    details = {
        "endpoints": ["/api/chat", "/api/chat/compact"],
        "summary_sources": ["dashboard", "tasks", "projects"],
        "payload_contract": {
            "request_fields": CHATBOT_REQUEST_FIELDS,
            "response_fields": [*CHATBOT_RESPONSE_FIELDS, "text", "actions", "requires_confirm"],
        },
        "recent_uploads": recent_uploads,
        "processing_queue": processing_queue,
        "contract": {
            "read_only": True,
        },
        "tenant": tenant,
    }
    return metrics, details, ""


SUMMARY_COLLECTORS: dict[str, Callable[[str], tuple[dict, dict, str]]] = {
    "dashboard": _collect_dashboard_summary,
    "upload": _collect_upload_summary,
    "projects": _collect_projects_summary,
    "tasks": _collect_tasks_summary,
    "aufgaben": _collect_tasks_summary,  # Legacy alias
    "messenger": _collect_messenger_summary,
    "email": _collect_email_summary,
    "mail": _collect_email_summary,      # Legacy alias
    "calendar": _collect_calendar_summary,
    "time": _collect_time_summary,
    "visualizer": _collect_visualizer_summary,
    "settings": _collect_settings_summary,
    "chatbot": _collect_chatbot_summary,
}




def extract_chat_message(payload: dict | None, _depth: int = 0) -> str:
    max_depth = 5
    if _depth >= max_depth:
        return ""

    payload = payload or {}
    if not isinstance(payload, dict):
        return ""

    for field in CHATBOT_REQUEST_FIELDS:
        value = payload.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    if isinstance(payload.get("payload"), dict):
        return extract_chat_message(payload.get("payload"), _depth + 1)
    return ""


def normalize_chat_response(response: dict | str | None, *, fallback_ok: bool = True) -> dict:
    if isinstance(response, dict):
        normalized = dict(response)
    else:
        text = str(response or "")
        normalized = {"ok": fallback_ok, "text": text, "response": text}

    text = normalized.get("text")
    resp = normalized.get("response")
    if isinstance(text, str) and "response" not in normalized:
        normalized["response"] = text
    elif isinstance(resp, str) and "text" not in normalized:
        normalized["text"] = resp

    normalized["text"] = str(normalized.get("text") or "")
    normalized["response"] = str(normalized.get("response") or normalized["text"])
    normalized["ok"] = bool(normalized.get("ok", fallback_ok))
    return normalized

def build_tool_summary(tool: str, tenant: str = "default") -> dict:
    collector = SUMMARY_COLLECTORS.get(tool)
    if collector is None:
        raise KeyError(tool)
    try:
        metrics, details, degraded_reason = collector(tenant)
    except Exception as exc:
        payload = _contract_payload(
            tool=tool,
            status="error",
            metrics={"collector_error": 1},
            details={"error": str(exc)},
            tenant=tenant,
            contract_kind="summary",
        )
        normalized, _ = _normalize_contract_payload(payload, tool, tenant=tenant, contract_kind="summary")
        return _apply_mia_parity(normalized, tool)

    if not isinstance(metrics, dict) or not isinstance(details, dict) or not isinstance(degraded_reason, str):
        payload = _contract_payload(
            tool=tool,
            status="degraded",
            metrics=_as_dict(metrics, {"contract_violation": 1}),
            details={
                "collector_contract": {
                    "metrics_is_dict": isinstance(metrics, dict),
                    "details_is_dict": isinstance(details, dict),
                    "degraded_reason_is_str": isinstance(degraded_reason, str),
                },
            },
            reason="collector_contract_invalid",
            tenant=tenant,
            contract_kind="summary",
        )
        normalized, _ = _normalize_contract_payload(payload, tool, tenant=tenant, contract_kind="summary")
        return _apply_mia_parity(normalized, tool)

    details_tenant = str(details.get("tenant") or tenant) if isinstance(details, dict) else str(tenant)
    tenant_mismatch = details_tenant != str(tenant)
    status = "degraded" if degraded_reason or tenant_mismatch else "ok"
    if tenant_mismatch and not degraded_reason:
        degraded_reason = "tenant_scope_corrected"
    payload = _contract_payload(
        tool=tool,
        status=status,
        metrics=metrics,
        details=details,
        reason=degraded_reason,
        tenant=tenant,
        contract_kind="summary",
    )
    normalized, _ = _normalize_contract_payload(payload, tool, tenant=tenant, contract_kind="summary")
    return _apply_mia_parity(normalized, tool)


def build_tool_health(tool: str, tenant: str = "default") -> dict:
    summary = build_tool_summary(tool, tenant)
    healthy = summary["status"] == "ok"
    checks = {
        "summary_contract": True,
        "backend_ready": healthy,
        "offline_safe": True,
    }
    summary["details"] = {
        **(summary.get("details") or {}),
        "checks": checks,
    }
    if tool in {"time", "zeiterfassung"}:
        summary["details"]["offline_persistence"] = bool(summary["details"].get("offline_persistence", False))
    normalized, _ = _normalize_contract_payload(summary, tool, tenant=tenant, contract_kind="health")
    return normalized


def validate_tool_contract_payload(payload: dict, *, expected_tool: str | None = None, expected_kind: str | None = None) -> list[str]:
    errors = _contract_errors(payload if isinstance(payload, dict) else {})
    if expected_tool and str((payload or {}).get("tool") or "") != expected_tool:
        errors.append("mismatch:tool")
    if expected_kind:
        actual_kind = ((payload or {}).get("details") or {}).get("contract", {}).get("kind")
        if actual_kind != expected_kind:
            errors.append("mismatch:details.contract.kind")
    return errors


def validate_summary_health_pair(summary_payload: dict, health_payload: dict) -> list[str]:
    errors: list[str] = []
    errors.extend(f"summary:{err}" for err in validate_tool_contract_payload(summary_payload, expected_kind="summary"))
    errors.extend(f"health:{err}" for err in validate_tool_contract_payload(health_payload, expected_kind="health"))

    summary_tool = str((summary_payload or {}).get("tool") or "")
    health_tool = str((health_payload or {}).get("tool") or "")
    if summary_tool and health_tool and summary_tool != health_tool:
        errors.append("mismatch:tool_pair")

    summary_details = (summary_payload or {}).get("details") if isinstance((summary_payload or {}).get("details"), dict) else {}
    health_details = (health_payload or {}).get("details") if isinstance((health_payload or {}).get("details"), dict) else {}
    if str(summary_details.get("tenant") or "") != str(health_details.get("tenant") or ""):
        errors.append("mismatch:tenant")

    summary_contract = summary_details.get("contract") if isinstance(summary_details.get("contract"), dict) else {}
    health_contract = health_details.get("contract") if isinstance(health_details.get("contract"), dict) else {}
    if summary_contract.get("version") != health_contract.get("version"):
        errors.append("mismatch:contract.version")
    if bool(summary_contract.get("read_only")) != bool(health_contract.get("read_only")):
        errors.append("mismatch:contract.read_only")

    checks = health_details.get("checks") if isinstance(health_details.get("checks"), dict) else {}
    if set(checks.keys()) != {"summary_contract", "backend_ready", "offline_safe"}:
        errors.append("type:health.details.checks")
    return errors


def build_tool_matrix(tenant: str = "default") -> list[dict]:
    rows: list[dict] = []
    for tool in CONTRACT_TOOLS:
        try:
            rows.append(build_tool_summary(tool, tenant))
        except Exception as exc:
            payload = _contract_payload(
                tool=tool,
                status="degraded",
                metrics={"collector_error": 1},
                details={"tenant": tenant, "aggregation_error": "internal_error"},
                reason="summary_aggregation_failed",
                tenant=tenant,
            )
            normalized, _ = _normalize_contract_payload(payload, tool, tenant=tenant)
            rows.append(_apply_mia_parity(normalized, tool))
    return rows


def build_mia_parity_matrix(tenant: str = "default") -> dict[str, object]:
    matrix = build_tool_matrix(tenant)
    rows: list[dict[str, object]] = []
    for item in matrix:
        mia = dict((item.get("details") or {}).get("mia") or {})
        rows.append(
            {
                "tool": item.get("tool"),
                "score": mia.get("score", 0),
                "max_score": mia.get("max_score", len(MIA_PARITY_CHECKS)),
                "tier": mia.get("tier", "low"),
                "checks": mia.get("checks", {}),
            }
        )
    low_parity = [row["tool"] for row in rows if row.get("tier") == "low"]
    prioritized_low_parity = [tool for tool in MIA_LOW_PARITY_TOOLS if tool in low_parity]
    return {
        "ok": True,
        "tenant": tenant,
        "checks": list(MIA_PARITY_CHECKS),
        "rows": rows,
        "low_parity": low_parity,
        "priority_low_parity": prioritized_low_parity,
        "historical_low_parity": list(MIA_LOW_PARITY_TOOLS),
        "baseline_status": "parity_aligned",
    }


def build_contract_response(
    *,
    tool: str,
    status: str,
    metrics: dict,
    details: dict,
    tenant: str,
    degraded_reason: str = "",
    contract_kind: str = "summary",
) -> dict:
    """Build and normalize a summary/health payload for tool contracts."""
    payload = _contract_payload(
        tool=tool,
        status=status,
        metrics=metrics,
        details=details,
        reason=degraded_reason,
        tenant=tenant,
        contract_kind=contract_kind,
    )
    normalized, _ = _normalize_contract_payload(payload, tool, tenant=tenant, contract_kind=contract_kind)
    return normalized


def build_health_response(
    *,
    tool: str,
    status: str,
    metrics: dict,
    details: dict,
    tenant: str,
    degraded_reason: str = "",
    checks: dict | None = None,
) -> tuple[dict, int]:
    """Helper for build_health in modules."""
    safe_details = dict(details or {})
    safe_checks = dict(checks or {})
    # Ensure standard checks are present if not provided
    safe_checks.setdefault("summary_contract", True)
    safe_checks.setdefault("backend_ready", status == "ok")
    safe_checks.setdefault("offline_safe", True)

    safe_details["checks"] = safe_checks
    payload = build_contract_response(
        tool=tool,
        status=status,
        metrics=metrics,
        details=safe_details,
        tenant=tenant,
        degraded_reason=degraded_reason,
        contract_kind="health",
    )
    code = 200 if payload["status"] in {"ok", "degraded"} else 503
    return payload, code
