from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Sequence

from .base_tool import BaseTool


@dataclass(frozen=True)
class ActionDefinition:
    name: str
    inputs_schema: Dict[str, Any]
    permissions: List[str]
    is_critical: bool
    risk_level: str  # LOW, MEDIUM, HIGH
    is_idempotent: bool
    audit_fields: List[str]
    tool_name: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "inputs_schema": self.inputs_schema,
            "permissions": list(self.permissions),
            "is_critical": self.is_critical,
            "risk_level": self.risk_level,
            "is_idempotent": self.is_idempotent,
            "audit_fields": list(self.audit_fields),
            "tool": self.tool_name,
        }


class ActionRegistry:
    """Catalog of all available actions across registered tools."""

    def __init__(self) -> None:
        self._actions_by_name: Dict[str, ActionDefinition] = {}

    def register_tool(self, tool: BaseTool) -> None:
        for action in tool.actions():
            definition = ActionDefinition(
                name=str(action["name"]),
                inputs_schema=dict(action.get("inputs_schema") or {"type": "object", "properties": {}}),
                permissions=list(action.get("permissions") or []),
                is_critical=bool(action.get("is_critical", False)),
                risk_level=str(action.get("risk_level", "LOW")),
                is_idempotent=bool(action.get("is_idempotent", False)),
                audit_fields=list(action.get("audit_fields") or []),
                tool_name=tool.name,
            )
            self._actions_by_name[definition.name] = definition

    def list_actions(self) -> List[Dict[str, Any]]:
        return [self._actions_by_name[name].to_dict() for name in sorted(self._actions_by_name)]

    def count(self) -> int:
        return len(self._actions_by_name)

    def search(self, query: str = "", *, critical_only: bool = False, permissions: Sequence[str] | None = None) -> List[Dict[str, Any]]:
        q = (query or "").strip().lower()
        required = set(permissions or [])
        matches: List[Dict[str, Any]] = []
        for action in self._actions_by_name.values():
            if q and q not in action.name.lower() and q not in action.tool_name.lower():
                continue
            if critical_only and not action.is_critical:
                continue
            if required and not required.issubset(set(action.permissions)):
                continue
            matches.append(action.to_dict())
        return sorted(matches, key=lambda item: item["name"])

    def tools_summary(self) -> Dict[str, int]:
        summary: Dict[str, int] = {}
        for action in self._actions_by_name.values():
            summary[action.tool_name] = summary.get(action.tool_name, 0) + 1
        return dict(sorted(summary.items()))


action_registry = ActionRegistry()
