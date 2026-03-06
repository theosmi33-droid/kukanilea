from __future__ import annotations

from typing import Any, Dict, Iterable, List


DEFAULT_ACTION_SUFFIXES: List[str] = [
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
]


class BaseTool:
    """
    Base class for all KUKANILEA tools.
    Inspired by llm-engineer-toolkit patterns.
    """

    name = "base"
    description = ""
    input_schema: Dict[str, Any] = {}
    default_permissions: List[str] = ["tenant:read"]
    default_audit_fields: List[str] = ["tenant_id", "user_id", "trace_id"]

    def actions(self) -> Iterable[Dict[str, Any]]:
        """
        Returns action metadata for action-registry ingestion.
        Tools may override this for highly specific actions.
        """

        base_schema = self.input_schema or {"type": "object", "properties": {}}
        for suffix in DEFAULT_ACTION_SUFFIXES:
            yield {
                "name": f"{self.name}.{suffix}",
                "inputs_schema": base_schema,
                "permissions": list(self.default_permissions),
                "is_critical": suffix in {"execute", "execute_async", "rollback", "cancel"},
                "audit_fields": list(self.default_audit_fields),
            }

    def run(self, **kwargs) -> Any:
        raise NotImplementedError("Tools must implement the run method.")
