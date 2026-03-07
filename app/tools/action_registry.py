from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Sequence

from .base_tool import BaseTool


@dataclass(frozen=True)
class ActionDefinition:
    action_id: str
    domain: str
    entity: str
    verb: str
    modifiers: List[str]
    tool: str
    parameter_schema: Dict[str, Any]
    permissions: List[str]
    confirm_required: bool
    audit_required: bool
    risk: str
    external_call: bool
    idempotency: str
    audit_fields: List[str]

    @property
    def name(self) -> str:
        """Legacy alias for action_id."""
        return self.action_id

    @property
    def inputs_schema(self) -> Dict[str, Any]:
        """Legacy alias for parameter_schema."""
        return self.parameter_schema

    @property
    def is_critical(self) -> bool:
        """Legacy alias for confirm_required."""
        return self.confirm_required

    @property
    def tool_name(self) -> str:
        """Legacy alias for tool."""
        return self.tool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "name": self.action_id,  # Legacy alias
            "domain": self.domain,
            "entity": self.entity,
            "verb": self.verb,
            "modifiers": list(self.modifiers),
            "tool": self.tool,
            "tool_name": self.tool,  # Legacy alias
            "parameter_schema": self.parameter_schema,
            "inputs_schema": self.parameter_schema,  # Legacy alias
            "permissions": list(self.permissions),
            "confirm_required": self.confirm_required,
            "is_critical": self.confirm_required,  # Legacy alias
            "audit_required": self.audit_required,
            "risk": self.risk,
            "external_call": self.external_call,
            "idempotency": self.idempotency,
            "audit_fields": list(self.audit_fields),
        }


class ActionRegistry:
    """Catalog of all available actions across registered tools."""

    def __init__(self) -> None:
        self._actions_by_id: Dict[str, ActionDefinition] = {}

    @property
    def _actions_by_name(self) -> Dict[str, ActionDefinition]:
        """Legacy alias for _actions_by_id."""
        return self._actions_by_id

    def register_tool(self, tool: BaseTool) -> None:
        for action in tool.actions():
            action_id = str(action.get("action_id") or action["name"])
            
            if action_id in self._actions_by_id:
                # Duplicate detection: Raise error to ensure single source of truth and uniqueness
                raise ValueError(f"Duplicate action_id detected: {action_id} (Tool: {tool.name})")

            # Validation: Write-actions MUST have confirm+audit
            verb = str(action.get("verb", action_id.split(".")[-1])).lower()
            is_write = verb in {
                "create", "update", "delete", "upsert", "patch", "purge", 
                "execute", "execute_async", "rollback", "cancel", "import", 
                "archive", "restore", "sync", "reconcile", "lock", "unlock"
            } or action.get("is_critical", False)
            
            confirm_required = bool(action.get("confirm_required", is_write))
            audit_required = bool(action.get("audit_required", is_write))
            
            # Policy completeness check
            if is_write and not (confirm_required and audit_required):
                raise ValueError(f"Write action {action_id} must have confirm_required and audit_required set to True")

            definition = ActionDefinition(
                action_id=action_id,
                domain=str(action.get("domain", tool.name.split("_")[0])),
                entity=str(action.get("entity", "default")),
                verb=verb,
                modifiers=list(action.get("modifiers") or []),
                tool=tool.name,
                parameter_schema=dict(action.get("parameter_schema") or action.get("inputs_schema") or {"type": "object", "properties": {}}),
                permissions=list(action.get("permissions") or []),
                confirm_required=confirm_required,
                audit_required=audit_required,
                risk=str(action.get("risk", "high" if is_write else "low")),
                external_call=bool(action.get("external_call", False)),
                idempotency=str(action.get("idempotency", "idempotent" if not is_write else "non-idempotent")),
                audit_fields=list(action.get("audit_fields") or []),
            )
            
            self._actions_by_id[action_id] = definition

    def list_actions(self) -> List[Dict[str, Any]]:
        return [self._actions_by_id[aid].to_dict() for aid in sorted(self._actions_by_id)]

    def count(self) -> int:
        return len(self._actions_by_id)

    def search(self, query: str = "", *, critical_only: bool = False, permissions: Sequence[str] | None = None) -> List[Dict[str, Any]]:
        q = (query or "").strip().lower()
        required = set(permissions or [])
        matches: List[Dict[str, Any]] = []
        for action in self._actions_by_id.values():
            if q and q not in action.action_id.lower() and q not in action.tool.lower():
                continue
            if critical_only and not action.confirm_required:
                continue
            if required and not required.issubset(set(action.permissions)):
                continue
            matches.append(action.to_dict())
        return sorted(matches, key=lambda item: item["action_id"])

    def tools_summary(self) -> Dict[str, int]:
        summary: Dict[str, int] = {}
        for action in self._actions_by_id.values():
            summary[action.tool] = summary.get(action.tool, 0) + 1
        return dict(sorted(summary.items()))


action_registry = ActionRegistry()
