from __future__ import annotations

import logging
from typing import Any, Dict

from app.tools.registry import registry
from app.security.approval_runtime import RuntimeApprovalPolicy, create_approval_challenge, validate_approval_token

logger = logging.getLogger("kukanilea.agents.executor")


class AgentExecutor:
    """
    Executes tools requested by agents with validation and logging.
    """

    def execute(self, tool_name: str, params: Dict[str, Any]) -> Any:
        tool = registry.get(tool_name)
        if not tool:
            logger.error(f"Execution failed: Tool '{tool_name}' not found.")
            raise ValueError(f"Tool '{tool_name}' not found in registry.")

        requires_confirm = bool(getattr(tool, "requires_confirm", False) or not getattr(tool, "read_only", False))
        policy = RuntimeApprovalPolicy(
            requires_confirm=requires_confirm,
            risk_level=str(getattr(tool, "risk_level", "medium")),
            approval_scope=f"agent_tool:{tool_name}",
            approval_ttl_seconds=int(getattr(tool, "approval_ttl_seconds", 120)),
            approval_subject=str(params.get("approval_subject") or "system"),
        )
        approved, reason = validate_approval_token(
            approval_token=params.get("approval_token"),
            policy=policy,
        )
        if not approved and policy.requires_confirm:
            challenge = create_approval_challenge(policy)
            logger.warning("Approval denied for tool '%s': %s", tool_name, reason)
            return {
                "error": "confirm_required",
                "tool": tool_name,
                "approval": {
                    "reason": reason,
                    "scope": policy.approval_scope,
                    "risk_level": policy.risk_level,
                    "approval_ttl_seconds": policy.approval_ttl_seconds,
                    "approval_subject": policy.approval_subject,
                    "challenge": challenge,
                },
            }

        logger.info(f"Executing tool: {tool_name} with params: {params}")
        try:
            return tool.run(**params)
        except Exception as e:
            logger.exception(f"Error during tool execution '{tool_name}': {e}")
            return {"error": str(e)}
