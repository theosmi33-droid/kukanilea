from __future__ import annotations

from datetime import UTC, datetime
from typing import Callable

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
CONTRACT_VERSION = "2026-03-05"


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
) -> dict:
    if status not in CONTRACT_STATUSES:
        status = "error"

    safe_metrics = dict(metrics or {})
    safe_details = dict(details or {})
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
        "tenant": tenant,
        "status": status,
        "updated_at": _now_iso(),
        "metrics": safe_metrics,
        "details": safe_details,
    }
    if status == "degraded":
        payload["degraded_reason"] = reason or "degraded_runtime"
    return payload


def _collect_dashboard_summary(tenant: str) -> tuple[dict, dict, str]:
    non_dashboard_tools = [tool for tool in CONTRACT_TOOLS if tool != "dashboard"]
    rows = [build_tool_summary(tool, tenant) for tool in non_dashboard_tools]
    degraded_tools = [row["tool"] for row in rows if row.get("status") == "degraded"]
    error_tools = [row["tool"] for row in rows if row.get("status") == "error"]
    metrics = {
        "total_tools": len(rows),
        "degraded_tools": len(degraded_tools),
        "error_tools": len(error_tools),
    }
    details = {
        "source": "contracts.tool_matrix",
        "tenant": tenant,
        "matrix_endpoint": "/api/dashboard/tool-matrix",
        "aggregate_mode": "summary_only",
        "degraded": degraded_tools,
        "errors": error_tools,
        "contract": {
            "read_only": True,
        },
    }
    return metrics, details, ""


def _collect_upload_summary(tenant: str) -> tuple[dict, dict, str]:
    list_pending = _core_get("list_pending")
    pending = list_pending() if callable(list_pending) else []
    metrics = {"pending_items": len(pending), "accepts_batch": 1}
    details = {"source": "core.list_pending", "tenant": tenant}
    reason = "pending_pipeline_unavailable" if not callable(list_pending) else ""
    return metrics, details, reason


def _collect_projects_summary(_tenant: str) -> tuple[dict, dict, str]:
    list_projects = _core_get("project_list")
    projects = list_projects() if callable(list_projects) else []
    metrics = {"total_projects": len(projects)}
    reason = "projects_backend_missing" if not callable(list_projects) else ""
    return metrics, {"source": "core.project_list"}, reason


def _collect_tasks_summary(_tenant: str) -> tuple[dict, dict, str]:
    task_list = _core_get("task_list")
    tasks = task_list() if callable(task_list) else []
    open_count = sum(1 for t in tasks if str(t.get("status", "")).lower() != "done") if tasks else 0
    metrics = {"tasks_total": len(tasks), "tasks_open": open_count}
    reason = "tasks_backend_missing" if not callable(task_list) else ""
    return metrics, {"source": "core.task_list"}, reason


def _collect_messenger_summary(_tenant: str) -> tuple[dict, dict, str]:
    metrics = {"confirm_gate": 1, "channels": 4}
    details = {
        "chat_endpoint": "/api/chat",
        "message_fields": ["q", "message", "msg"],
        "confirm_gate": True,
    }
    return metrics, details, ""


def _collect_email_summary(_tenant: str) -> tuple[dict, dict, str]:
    metrics = {"draft_supported": 1, "send_supported": 1}
    details = {"draft_endpoint": "/api/mail/draft", "eml_endpoint": "/api/mail/eml"}
    return metrics, details, ""


def _collect_calendar_summary(_tenant: str) -> tuple[dict, dict, str]:
    reminders_due = _core_get("knowledge_calendar_reminders_due")
    reminders = reminders_due(_tenant) if callable(reminders_due) else []
    metrics = {"due_reminders": len(reminders), "ics_export": 1}
    reason = "calendar_source_missing" if not callable(reminders_due) else ""
    return metrics, {"source": "core.knowledge_calendar_reminders_due"}, reason


def _collect_time_summary(tenant: str) -> tuple[dict, dict, str]:
    time_entry_list = _core_get("time_entry_list")
    entries = time_entry_list(tenant=tenant) if callable(time_entry_list) else []
    running = sum(1 for e in entries if not e.get("ended_at")) if entries else 0
    metrics = {"entries": len(entries), "running": running}
    reason = "time_tracking_unavailable" if not callable(time_entry_list) else ""
    return metrics, {"source": "core.time_entry_list", "tenant": tenant}, reason


def _collect_visualizer_summary(_tenant: str) -> tuple[dict, dict, str]:
    build_visualizer_payload = _core_get("build_visualizer_payload")
    metrics = {"sources_endpoint": 1, "summary_endpoint": 1}
    reason = "visualizer_logic_missing" if not callable(build_visualizer_payload) else ""
    return metrics, {"source": "core.build_visualizer_payload"}, reason


def _collect_settings_summary(_tenant: str) -> tuple[dict, dict, str]:
    metrics = {"security_headers": 1, "admin_tools": 1}
    details = {"pages": ["/settings", "/admin/logs", "/admin/audit"]}
    return metrics, details, ""


def _collect_chatbot_summary(_tenant: str) -> tuple[dict, dict, str]:
    metrics = {"overlay": 1, "compact_api": 1}
    details = {
        "endpoints": ["/api/chat", "/api/chat/compact"],
        "payload_contract": {
            "request_fields": CHATBOT_REQUEST_FIELDS,
            "response_fields": CHATBOT_RESPONSE_FIELDS,
        },
        "contract": {
            "read_only": True,
        },
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
        return _contract_payload(
            tool=tool,
            status="error",
            metrics={"collector_error": 1},
            details={"error": str(exc)},
            tenant=tenant,
        )

    status = "degraded" if degraded_reason else "ok"
    safe_details = dict(details or {})
    safe_details.setdefault("tenant", tenant)
    return _contract_payload(
        tool=tool,
        status=status,
        metrics=metrics,
        details=safe_details,
        reason=degraded_reason,
        tenant=tenant,
    )


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
    return summary


def build_tool_matrix(tenant: str = "default") -> list[dict]:
    return [build_tool_summary(tool, tenant) for tool in CONTRACT_TOOLS]
