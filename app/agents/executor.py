from __future__ import annotations

import logging
from typing import Any, Dict

from app.mia_audit import (
    MIA_EVENT_EXTERNAL_CALL_BLOCKED,
    MIA_EVENT_PARAMETER_VALIDATION_FAILED,
    MIA_EVENT_ROUTE_BLOCKED,
    MIA_EVENT_ROUTE_EXECUTED,
    canonical_mia_payload,
    emit_mia_event_safe,
)
from app.tools.registry import registry

logger = logging.getLogger("kukanilea.agents.executor")


class AgentExecutor:
    """
    Executes tools requested by agents with validation and logging.
    """

    def execute(self, tool_name: str, params: Dict[str, Any]) -> Any:
        tenant_id = str(params.get("tenant_id") or params.get("tenant") or "KUKANILEA") if isinstance(params, dict) else "KUKANILEA"
        user_id = str(params.get("user_id") or params.get("actor") or "system") if isinstance(params, dict) else "system"

        if not isinstance(params, dict):
            emit_mia_event_safe(
                event_type=MIA_EVENT_PARAMETER_VALIDATION_FAILED,
                entity_type="agent_executor",
                entity_ref=str(tool_name or "unknown"),
                tenant_id=tenant_id,
                payload=canonical_mia_payload(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    action=str(tool_name or "unknown"),
                    status="failed",
                    risk="medium",
                    meta={"reason": "params_not_dict"},
                ),
            )
            raise ValueError("params must be a dict")

        if str(tool_name or "").startswith(("http.", "https.", "external.")):
            emit_mia_event_safe(
                event_type=MIA_EVENT_EXTERNAL_CALL_BLOCKED,
                entity_type="agent_executor",
                entity_ref=str(tool_name or "unknown"),
                tenant_id=tenant_id,
                payload=canonical_mia_payload(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    action=str(tool_name or "unknown"),
                    status="blocked",
                    risk="high",
                    meta={"reason": "external_tools_disallowed"},
                ),
            )
            raise PermissionError("external_tool_calls_blocked")

        tool = registry.get(tool_name)
        if not tool:
            logger.error(f"Execution failed: Tool '{tool_name}' not found.")
            emit_mia_event_safe(
                event_type=MIA_EVENT_ROUTE_BLOCKED,
                entity_type="agent_executor",
                entity_ref=str(tool_name or "unknown"),
                tenant_id=tenant_id,
                payload=canonical_mia_payload(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    action=str(tool_name or "unknown"),
                    status="blocked",
                    risk="medium",
                    meta={"reason": "tool_not_found"},
                ),
            )
            raise ValueError(f"Tool '{tool_name}' not found in registry.")

        logger.info(f"Executing tool: {tool_name} with params: {params}")
        try:
            result = tool.run(**params)
            emit_mia_event_safe(
                event_type=MIA_EVENT_ROUTE_EXECUTED,
                entity_type="agent_executor",
                entity_ref=str(tool_name or "unknown"),
                tenant_id=tenant_id,
                payload=canonical_mia_payload(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    action=str(tool_name or "unknown"),
                    status="executed",
                    risk="medium" if bool(params) else "low",
                ),
            )
            return result
        except Exception as e:
            logger.exception(f"Error during tool execution '{tool_name}': {e}")
            return {"error": str(e)}
