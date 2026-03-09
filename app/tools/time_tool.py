from __future__ import annotations

from typing import Any

from app.tools.base_tool import BaseTool
from app.tools.registry import registry
from app.tools.shared_services import get_tenant_id


def _resolve_tenant_id(requested_tenant_id: str | None) -> str | None:
    active_tenant_id = get_tenant_id()
    if not active_tenant_id:
        return None
    if requested_tenant_id and requested_tenant_id != active_tenant_id:
        raise PermissionError("tenant_mismatch")
    return active_tenant_id


class TimeTool(BaseTool):
    """
    Manages work time tracking, timers, and reports.
    """

    name = "time"
    domain = "time"
    entities = ["time_entry", "timer", "project", "report", "approval", "export", "billing", "budget", "category", "tag"]
    description = "Startet oder stoppt eine Zeiterfassung für ein Projekt."
    input_schema = {
        "type": "object",
        "properties": {
            "tenant_id": {"type": "string"},
            "project_id": {"type": "string"},
            "task_id": {"type": "string"},
            "description": {"type": "string"},
            "action": {"type": "string", "enum": ["start", "stop", "list"], "default": "start"}
        },
        "required": ["tenant_id", "action"]
    }

    def run(self, tenant_id: str, action: str = "start", project_id: str | None = None, task_id: str | None = None, description: str = "") -> Any:
        resolved_tenant_id = _resolve_tenant_id(tenant_id)
        if not resolved_tenant_id:
            return {"status": "error", "error": "tenant_context_missing", "message": "No tenant context found."}

        if action == "start":
            # Call core logic
            try:
                # from app.core.logic import time_entry_start
                # time_entry_start(resolved_tenant_id, project_id, task_id, description)
                return {"status": "started", "tenant_id": resolved_tenant_id, "project_id": project_id, "action": "track_time"}
            except Exception as e:
                return {"status": "error", "message": str(e)}
        return {"status": "ok", "action": action, "tenant_id": resolved_tenant_id}

# Register tool
registry.register(TimeTool())
