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
    level: int  # 1 (READ), 2 (VOLATILE), 3 (MODIFICATION), 4 (DESTRUCTIVE)
    external_call: bool
    idempotency: str
    audit_fields: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "name": self.action_id,  # Legacy alias
            "domain": self.domain,
            "entity": self.entity,
            "verb": self.verb,
            "modifiers": list(self.modifiers),
            "tool": self.tool,
            "parameter_schema": self.parameter_schema,
            "inputs_schema": self.parameter_schema,  # Legacy alias
            "permissions": list(self.permissions),
            "confirm_required": self.confirm_required,
            "is_critical": self.confirm_required or self.level >= 3,  # Compatibility
            "audit_required": self.audit_required,
            "risk": self.risk,
            "level": self.level,
            "external_call": self.external_call,
            "idempotency": self.idempotency,
            "audit_fields": list(self.audit_fields),
        }

    @property
    def is_critical(self) -> bool:
        return self.confirm_required or self.level >= 3

    @property
    def inputs_schema(self) -> Dict[str, Any]:
        return self.parameter_schema


class ActionRegistry:
    """Catalog of all available actions across registered tools."""

    def __init__(self) -> None:
        self._actions_by_id: Dict[str, ActionDefinition] = {}

    @property
    def _actions_by_name(self) -> Dict[str, ActionDefinition]:
        return self._actions_by_id

    def register_tool(self, tool: BaseTool) -> None:
        for action in tool.actions():
            action_id = str(action.get("action_id") or action["name"])
            
            if action_id in self._actions_by_id:
                # Duplicate detection: Raise error to ensure single source of truth and uniqueness
                raise ValueError(f"Duplicate action_id detected: {action_id} (Tool: {tool.name})")

            # Validation: Write-actions MUST have confirm+audit
            raw_verb = str(action.get("verb") or action_id.split(".")[-1]).lower()
            
            # Check for explicit write indicators in metadata
            meta_is_critical = bool(action.get("is_critical", False))
            meta_is_write = action.get("action_type") == "write" or action.get("action_type") == "high_risk"
            
            # Refined verb detection: check for destructive keywords anywhere in the verb string
            is_destructive = any(k in raw_verb for k in {"delete", "purge", "rollback", "cancel", "destroy", "drop"})
            is_write = any(k in raw_verb for k in {
                "create", "update", "upsert", "patch", 
                "execute", "import", "archive", "restore", 
                "sync", "reconcile", "lock", "unlock"
            }) or is_destructive or meta_is_critical or meta_is_write
            
            # Determine LEVEL (1-4) according to AGENTS.md
            level = 1
            if is_destructive or (action.get("action_type") == "high_risk"):
                level = 4
            elif is_write:
                level = 3
            elif any(k in raw_verb for k in {"list", "search", "get", "aggregate", "read"}) or action.get("action_type") == "read":
                level = 1
            
            confirm_required = bool(action.get("confirm_required", level >= 3))
            audit_required = bool(action.get("audit_required", level >= 3))
            
            # Policy completeness check
            if level >= 3 and not (confirm_required and audit_required):
                raise ValueError(f"Write action {action_id} (Level {level}) must have confirm_required and audit_required set to True")

            definition = ActionDefinition(
                action_id=action_id,
                domain=str(action.get("domain", tool.name.split("_")[0])),
                entity=str(action.get("entity", "default")),
                verb=raw_verb,
                modifiers=list(action.get("modifiers") or []),
                tool=tool.name,
                parameter_schema=dict(action.get("parameter_schema") or action.get("inputs_schema") or {"type": "object", "properties": {}}),
                permissions=list(action.get("permissions") or []),
                confirm_required=confirm_required,
                audit_required=audit_required,
                risk=str(action.get("risk", "high" if level >= 3 else "low")),
                level=level,
                external_call=bool(action.get("external_call", False)),
                idempotency=str(action.get("idempotency", "idempotent" if level < 3 else "non-idempotent")),
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
