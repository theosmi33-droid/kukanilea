from __future__ import annotations

from typing import Any, Dict, Optional
from app.tools.base_tool import BaseTool
from app.tools.registry import registry

class WorkItemTool(BaseTool):
    """
    Converts messages or context into structured work items (Tasks or Projects).
    """

    name = "work_item"
    domain = "tasks"
    entities = ["task", "project", "milestone", "assignment", "status", "deadline", "comment", "attachment", "priority", "label"]
    description = "Erstellt aus einer Nachricht oder einem Kontext einen Task oder ein Projekt."
    input_schema = {
        "type": "object",
        "properties": {
            "target": {"type": "string", "enum": ["task", "project"], "default": "task"},
            "confirm_gate": {"type": "boolean", "default": True},
            "priority": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH"], "default": "MEDIUM"}
        },
        "required": ["target"]
    }

    def run(self, target: str = "task", confirm_gate: bool = True, priority: str = "MEDIUM") -> Any:
        # Mock creation with confirm-gate requirement
        return {
            "status": "pending_confirmation",
            "target": target,
            "priority": priority,
            "confirm_gate_required": confirm_gate,
            "details": f"{target.capitalize()} wurde zur Bestätigung vorgemerkt."
        }

# Register tool
registry.register(WorkItemTool())
