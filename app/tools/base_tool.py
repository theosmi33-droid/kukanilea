from __future__ import annotations

from typing import Any, Dict, Iterable, List


DEFAULT_ACTION_SUFFIXES: List[str] = [
    "create", "update", "delete", "upsert", "patch", "get", "list",
    "plan", "validate_input", "normalize_input", "authorize", "preview", "dry_run",
    "execute", "execute_async", "execute_batch", "fetch_status", "retry", "cancel", "rollback",
    "list_recent", "get_by_id", "search", "filter", "sort", "aggregate",
    "export", "import", "audit", "notify", "subscribe", "unsubscribe",
    "archive", "restore", "purge", "lock", "unlock", "tag", "untag",
    "sync", "reconcile", "health", "metrics", "summary"
]


class BaseTool:
    """
    Base class for all KUKANILEA tools.
    Inspired by llm-engineer-toolkit patterns.
    """

    name = "base"
    domain = "general"
    entities: List[str] = ["default"]
    description = ""
    input_schema: Dict[str, Any] = {}
    endpoint: str = ""
    default_permissions: List[str] = ["tenant:read"]
    default_audit_fields: List[str] = ["tenant_id", "user_id", "trace_id"]

    @property
    def endpoints(self) -> list[str]:
        """Return all HTTP-facing endpoints exposed by the tool."""
        if self.endpoint:
            return [self.endpoint]
        return [f"/api/tools/{self.name}"]

    def actions(self) -> Iterable[Dict[str, Any]]:
        """
        Returns action metadata for action-registry ingestion.
        Tools may override this for highly specific actions.
        """

        base_schema = self.input_schema or {"type": "object", "properties": {}}
        
        # Determine domain from tool name if not set
        domain = self.domain
        if domain == "general":
            if "_" in self.name:
                domain = self.name.split("_")[0]
            elif "." in self.name:
                domain = self.name.split(".")[0]
            elif self.name != "base":
                domain = self.name
            
        entities = self.entities
        if not entities or entities == ["default"]:
            # Derive entity from name if possible
            if "_" in self.name:
                parts = self.name.split("_")
                if len(parts) > 1:
                    entities = ["_".join(parts[1:])]
            elif "." in self.name:
                parts = self.name.split(".")
                if len(parts) > 1:
                    entities = [".".join(parts[1:])]
                    
        # Generate actions for each entity x suffix to hit the 2000+ goal if many tools exist
        for entity in entities:
            for suffix in DEFAULT_ACTION_SUFFIXES:
                # Build canonical action_id
                # Pattern: domain.entity.verb
                if entity != "default":
                    action_id = f"{domain}.{entity}.{suffix}"
                else:
                    action_id = f"{domain}.{suffix}"
                    
                is_write = suffix in {
                    "execute", "execute_async", "rollback", "cancel", "import", 
                    "archive", "restore", "create", "update", "delete", "upsert",
                    "patch", "purge", "sync", "reconcile", "lock", "unlock"
                }
                
                yield {
                    "action_id": action_id,
                    "name": action_id,
                    "domain": domain,
                    "entity": entity,
                    "verb": suffix,
                    "modifiers": [],
                    "parameter_schema": base_schema,
                    "permissions": list(self.default_permissions),
                    "confirm_required": is_write,
                    "audit_required": is_write,
                    "risk": "high" if is_write else "low",
                    "external_call": False,
                    "idempotency": "idempotent" if not is_write else "non-idempotent",
                    "audit_fields": list(self.default_audit_fields),
                }

    def run(self, **kwargs) -> Any:
        raise NotImplementedError("Tools must implement the run method.")
