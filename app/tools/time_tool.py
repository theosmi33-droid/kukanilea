from __future__ import annotations

from typing import Any, Dict
from app.tools.base_tool import BaseTool
from app.tools.registry import registry

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
        if action == "start":
            # Call core logic
            try:
                # from app.core.logic import time_entry_start
                # time_entry_start(tenant_id, project_id, task_id, description)
                return {"status": "started", "tenant_id": tenant_id, "project_id": project_id, "action": "track_time"}
            except Exception as e:
                return {"status": "error", "message": str(e)}
        return {"status": "ok", "action": action}

# Register tool
registry.register(TimeTool())
