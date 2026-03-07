from __future__ import annotations

from typing import Any, Dict, Iterable, List


DEFAULT_ACTION_SUFFIXES: List[str] = [
    "create",
    "update",
    "delete",
    "upsert",
    "patch",
    "get",
    "list",
    "plan",
    "validate_input",
    "normalize_input",
    "authorize",
    "preview",
    "dry_run",
    "execute",
    "execute_async",
    "execute_batch",
    "fetch_status",
    "retry",
    "cancel",
    "rollback",
    "list_recent",
    "get_by_id",
    "search",
    "export",
    "import",
    "audit",
    "notify",
    "archive",
    "restore",
    "lock",
    "unlock",
    "reconcile",
    "sync",
    "analyze",
    "summarize",
    "verify",
    "purge",
    "migrate",
    "clone",
    "share",
    "publish",
    "subscribe",
    "unsubscribe",
    "calculate",
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
        Multiplies default suffixes across all defined entities.
        """
        base_schema = self.input_schema or {"type": "object", "properties": {}}
        
        domain = self.domain
        if domain == "general":
            if "_" in self.name:
                domain = self.name.split("_")[0]
            elif "." in self.name:
                domain = self.name.split(".")[0]
            else:
                domain = self.name

        for entity in self.entities:
            for suffix in DEFAULT_ACTION_SUFFIXES:
                action_id = f"{domain}.{entity}.{suffix}"
                
                # Suffixes that typically imply writes
                is_write = suffix in {
                    "create", "update", "delete", "upsert", "patch",
                    "execute", "execute_async", "execute_batch",
                    "rollback", "cancel", "import", "archive", "restore",
                    "lock", "unlock", "reconcile", "sync", "purge", "migrate"
                }
                
                yield {
                    "action_id": action_id,
                    "name": action_id,
                    "domain": domain,
                    "entity": entity,
                    "verb": suffix,
                    "inputs_schema": base_schema,
                    "parameter_schema": base_schema,
                    "permissions": list(self.default_permissions),
                    "is_critical": is_write,
                    "audit_fields": list(self.default_audit_fields),
                }

    def run(self, **kwargs) -> Any:
        raise NotImplementedError("Tools must implement the run method.")
