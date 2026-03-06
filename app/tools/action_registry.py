from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Any, Dict, List, Sequence

from .base_tool import BaseTool

DEFAULT_OUTPUT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "status": {"type": "string"},
        "data": {"type": ["object", "array", "null"]},
    },
    "required": ["status"],
}

DOMAIN_ENTITIES: Dict[str, tuple[str, ...]] = {
    "calendar": ("event", "attendee", "availability", "reminder", "schedule", "timeline", "meeting", "slot", "resource", "timezone"),
    "filesystem": ("file", "folder", "document", "archive", "permission", "snapshot", "path", "asset", "share", "version"),
    "mail": ("message", "thread", "draft", "attachment", "mailbox", "contact", "label", "folder", "signature", "recipient"),
    "memory": ("memory_item", "insight", "fact", "session", "vector", "tag", "summary", "reference", "correction", "context"),
    "mesh": ("node", "sync_job", "channel", "tenant", "snapshot", "signal", "event", "peer", "state", "queue"),
    "messenger": ("chat", "channel", "message", "participant", "template", "reaction", "thread", "media", "delivery", "profile"),
    "work_item": ("task", "project", "milestone", "backlog", "comment", "assignment", "status", "estimate", "dependency", "board"),
    "lexoffice": ("invoice", "contact", "line_item", "tax_profile", "voucher", "payment", "ledger", "document", "booking", "receipt"),
    "zugferd": ("invoice", "xml_payload", "pdf_payload", "validation_result", "export_job", "schema", "attachment", "counterparty", "currency", "compliance"),
    "retrieve_corrections": ("correction", "rule", "dataset", "query", "result", "evidence", "diff", "snapshot", "signal", "issue"),
    "planning": ("plan", "step", "workflow", "proposal", "policy", "checkpoint", "handoff", "execution", "note", "route"),
}

CORE_VERBS: tuple[str, ...] = (
    "list",
    "get",
    "search",
    "summarize",
    "preview",
    "validate",
    "plan",
    "simulate",
    "create",
    "update",
    "upsert",
    "delete",
    "archive",
    "restore",
    "approve",
    "execute",
    "cancel",
    "export",
)

MODIFIERS: tuple[str, ...] = ("default", "safe", "batch", "async")
WRITE_VERBS = {"create", "update", "upsert", "delete", "archive", "restore", "approve", "execute", "cancel"}
HIGH_RISK_VERBS = {"delete", "approve", "execute", "cancel"}


@dataclass(frozen=True)
class ActionSpec:
    action_id: str
    domain: str
    entity: str
    verb: str
    modifier: str
    description: str
    params_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    requires_confirm: bool
    risk_level: str
    audit_event_type: str
    idempotency_key_strategy: str
    enabled: bool
    tags: List[str]
    tool_name: str
    source_action_name: str
    permissions: List[str]
    is_critical: bool
    audit_fields: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.action_id,
            "action_id": self.action_id,
            "domain": self.domain,
            "entity": self.entity,
            "verb": self.verb,
            "modifier": self.modifier,
            "description": self.description,
            "inputs_schema": self.params_schema,
            "params_schema": self.params_schema,
            "output_schema": self.output_schema,
            "requires_confirm": self.requires_confirm,
            "risk_level": self.risk_level,
            "audit_event_type": self.audit_event_type,
            "idempotency_key_strategy": self.idempotency_key_strategy,
            "enabled": self.enabled,
            "tags": list(self.tags),
            "permissions": list(self.permissions),
            "is_critical": self.is_critical,
            "audit_fields": list(self.audit_fields),
            "tool": self.tool_name,
            "source_action_name": self.source_action_name,
        }


class ActionRegistry:
    """Deterministic metadata-driven registry for MIA actions."""

    def __init__(self) -> None:
        self._actions_by_id: Dict[str, ActionSpec] = {}
        self._tool_metadata_by_domain: Dict[str, Dict[str, Any]] = {}

    def register_tool(self, tool: BaseTool) -> None:
        tool_actions = list(tool.actions())
        if not tool_actions:
            return

        domain = self._resolve_domain(tool.name)
        first_action = tool_actions[0]
        self._tool_metadata_by_domain[domain] = {
            "tool_name": tool.name,
            "source_action_name": str(first_action.get("name") or f"{tool.name}.execute"),
            "params_schema": dict(first_action.get("inputs_schema") or {"type": "object", "properties": {}}),
            "permissions": list(first_action.get("permissions") or []),
            "audit_fields": list(first_action.get("audit_fields") or []),
            "is_critical": bool(first_action.get("is_critical", False)),
        }
        self._rebuild_actions()

    def _rebuild_actions(self) -> None:
        self._actions_by_id = {}

        for domain, entities in DOMAIN_ENTITIES.items():
            tool_meta = self._tool_metadata_by_domain.get(
                domain,
                {
                    "tool_name": f"mia.{domain}",
                    "source_action_name": f"mia.{domain}.execute",
                    "params_schema": {"type": "object", "properties": {}},
                    "permissions": ["tenant:read"],
                    "audit_fields": ["tenant_id", "trace_id"],
                    "is_critical": False,
                },
            )

            for entity, verb, modifier in product(entities, CORE_VERBS, MODIFIERS):
                action_id = f"{domain}.{entity}.{verb}.{modifier}"
                risk_level = self._risk_level_for(verb)
                requires_confirm = verb in WRITE_VERBS
                spec = ActionSpec(
                    action_id=action_id,
                    domain=domain,
                    entity=entity,
                    verb=verb,
                    modifier=modifier,
                    description=f"{verb} {entity} in {domain} via {modifier} mode.",
                    params_schema=tool_meta["params_schema"],
                    output_schema=dict(DEFAULT_OUTPUT_SCHEMA),
                    requires_confirm=requires_confirm,
                    risk_level=risk_level,
                    audit_event_type=f"{domain}.{entity}.{verb}",
                    idempotency_key_strategy="tenant_action_payload_hash" if verb in WRITE_VERBS else "tenant_action_window",
                    enabled=True,
                    tags=[domain, entity, verb, modifier, risk_level],
                    tool_name=tool_meta["tool_name"],
                    source_action_name=tool_meta["source_action_name"],
                    permissions=tool_meta["permissions"],
                    is_critical=bool(tool_meta["is_critical"] or verb in HIGH_RISK_VERBS),
                    audit_fields=tool_meta["audit_fields"],
                )
                self._actions_by_id[action_id] = spec

    def _resolve_domain(self, tool_name: str) -> str:
        if tool_name in DOMAIN_ENTITIES:
            return tool_name
        if tool_name.startswith("memory"):
            return "memory"
        if tool_name.startswith("calendar"):
            return "calendar"
        if tool_name.startswith("retrieve"):
            return "retrieve_corrections"
        return "planning"

    def _risk_level_for(self, verb: str) -> str:
        if verb in HIGH_RISK_VERBS:
            return "high"
        if verb in WRITE_VERBS:
            return "medium"
        return "low"

    def list_actions(self) -> List[Dict[str, Any]]:
        return [self._actions_by_id[name].to_dict() for name in sorted(self._actions_by_id)]

    def count(self) -> int:
        return len(self._actions_by_id)

    def search(self, query: str = "", *, critical_only: bool = False, permissions: Sequence[str] | None = None) -> List[Dict[str, Any]]:
        q = (query or "").strip().lower()
        required = set(permissions or [])
        matches: List[Dict[str, Any]] = []
        for action in self._actions_by_id.values():
            if q and q not in action.action_id.lower() and q not in action.tool_name.lower() and q not in action.description.lower():
                continue
            if critical_only and not action.is_critical:
                continue
            if required and not required.issubset(set(action.permissions)):
                continue
            matches.append(action.to_dict())
        return sorted(matches, key=lambda item: item["action_id"])

    def tools_summary(self) -> Dict[str, int]:
        summary: Dict[str, int] = {}
        for action in self._actions_by_id.values():
            summary[action.tool_name] = summary.get(action.tool_name, 0) + 1
        return dict(sorted(summary.items()))

    def domain_summary(self) -> Dict[str, int]:
        summary: Dict[str, int] = {}
        for action in self._actions_by_id.values():
            summary[action.domain] = summary.get(action.domain, 0) + 1
        return dict(sorted(summary.items()))


action_registry = ActionRegistry()
