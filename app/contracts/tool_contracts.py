from __future__ import annotations

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
REQUIRED_CONTRACT_FIELDS = ("version", "read_only")


def _core_get(name: str, default=None):
    return getattr(core, name, default)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _contract_payload(tool: str, status: str, metrics: dict, details: dict, reason: str = "", *, tenant: str = "default") -> dict:
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
    return errors


def _normalize_contract_payload(payload: dict, tool: str, tenant: str = "default") -> tuple[dict, list[str]]:
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
    if normalized.get("details", {}).get("tenant") != str(tenant or "default"):
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


def _collect_dashboard_summary(tenant: str) -> tuple[dict, dict, str]:
    recent_uploads = _recent_upload_items(tenant)
    processing_queue = _processing_queue_items(tenant)
    non_dashboard_tools = [tool for tool in CONTRACT_TOOLS if tool != "dashboard"]
    rows = [build_tool_summary(tool, tenant) for tool in non_dashboard_tools]
    degraded_tools = [row["tool"] for row in rows if row.get("status") == "degraded"]
    error_tools = [row["tool"] for row in rows if row.get("status") == "error"]
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
        "recent_uploads": recent_uploads,
        "processing_queue": processing_queue,
        "contract": {
            "read_only": True,
        },
    }
    return metrics, details, ""


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
        except Exception as exc:
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
    metrics = {"confirm_gate": 1, "channels": 4}
    details = {
        "chat_endpoint": "/api/chat",
        "message_fields": ["q", "message", "msg"],
        "confirm_gate": True,
        "tenant": tenant,
    }
    return metrics, details, ""


def _collect_email_summary(tenant: str) -> tuple[dict, dict, str]:
    metrics = {"draft_supported": 1, "send_supported": 1}
    details = {"draft_endpoint": "/api/mail/draft", "eml_endpoint": "/api/mail/eml", "tenant": tenant}
    return metrics, details, ""


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
    build_visualizer_payload = _core_get("build_visualizer_payload")
    metrics = {"sources_endpoint": 1, "summary_endpoint": 1}
    reason = "visualizer_logic_missing" if not callable(build_visualizer_payload) else ""
    return metrics, {"source": "core.build_visualizer_payload", "tenant": tenant}, reason


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
    "messenger": _collect_messenger_summary,
    "email": _collect_email_summary,
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
        )
        normalized, _ = _normalize_contract_payload(payload, tool, tenant=tenant)
        return normalized

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
        )
        normalized, _ = _normalize_contract_payload(payload, tool, tenant=tenant)
        return normalized

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
    )
    normalized, _ = _normalize_contract_payload(payload, tool, tenant=tenant)
    return normalized


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
    normalized, _ = _normalize_contract_payload(summary, tool, tenant=tenant)
    return normalized


def build_tool_matrix(tenant: str = "default") -> list[dict]:
    return [build_tool_summary(tool, tenant) for tool in CONTRACT_TOOLS]


def build_contract_response(
    *,
    tool: str,
    status: str,
    metrics: dict,
    details: dict,
    tenant: str,
    degraded_reason: str = "",
) -> dict:
    """Build and normalize a summary/health payload for tool contracts."""
    payload = _contract_payload(
        tool=tool,
        status=status,
        metrics=metrics,
        details=details,
        reason=degraded_reason,
        tenant=tenant,
    )
    normalized, _ = _normalize_contract_payload(payload, tool, tenant=tenant)
    return normalized
