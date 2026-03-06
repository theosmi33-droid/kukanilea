from __future__ import annotations

from typing import Any, Dict, Iterable, List


DEFAULT_ACTION_SUFFIXES: List[str] = [
    "create",
    "read",
    "update",
    "delete",
    "send",
    "upload",
    "search",
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
    "export",
    "import",
    "audit",
    "notify",
    "archive",
    "restore",
]


class BaseTool:
    """
    Base class for all KUKANILEA tools.
    Inspired by llm-engineer-toolkit patterns.
    """

    name = "base"
    domain = "CORE"
    entity = "GENERIC"
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
        for suffix in DEFAULT_ACTION_SUFFIXES:
            # Transition to DOMAIN.ENTITY.VERB hierarchy
            verb = suffix.upper()
            action_name = f"{self.domain}.{self.entity}.{verb}"

            # Classification logic based on suffix
            is_mutate = suffix in {"create", "update", "delete", "send", "upload", "execute", "execute_async", "rollback", "cancel", "archive", "restore", "import"}
            is_critical = suffix in {"execute", "execute_async", "rollback", "cancel", "delete"}
            risk_level = "HIGH" if is_critical else "MEDIUM" if is_mutate else "LOW"
            is_idempotent = suffix in {"read", "search", "list", "plan", "validate_input", "normalize_input", "preview", "dry_run", "fetch_status", "list_recent", "get_by_id", "export", "audit", "rollback", "cancel", "archive", "restore"}

            yield {
                "name": action_name,
                "tool_name": self.name,
                "suffix": suffix,
                "inputs_schema": base_schema,
                "permissions": list(self.default_permissions),
                "is_critical": is_critical,
                "risk_level": risk_level,
                "is_idempotent": is_idempotent,
                "audit_fields": list(self.default_audit_fields),
            }

    def run(self, **kwargs) -> Any:
        raise NotImplementedError("Tools must implement the run method.")
