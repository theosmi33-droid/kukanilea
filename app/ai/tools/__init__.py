from __future__ import annotations

from typing import Any

from app.agents import tools as agent_tools

ALLOWED_TOOL_NAMES = ("search_contacts", "search_documents", "create_task")


def ollama_tools() -> list[dict[str, Any]]:
    return agent_tools.ollama_tool_definitions(allowed_names=list(ALLOWED_TOOL_NAMES))


def execute_tool(
    *,
    name: str,
    args: dict[str, Any],
    tenant_id: str,
    user_id: str,
    read_only: bool,
) -> dict[str, Any]:
    if str(name or "") not in ALLOWED_TOOL_NAMES:
        return {
            "result": {},
            "error": {"code": "unknown_tool", "msg": f"Unbekanntes Tool: {name}"},
        }
    return agent_tools.dispatch(
        name,
        args or {},
        read_only_flag=bool(read_only),
        tenant_id=str(tenant_id or ""),
        user=str(user_id or "system"),
    )
