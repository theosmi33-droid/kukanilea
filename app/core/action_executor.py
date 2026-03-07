from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable

logger = logging.getLogger("kukanilea.core.action_executor")

ActionFn = Callable[[dict[str, Any]], Any]


@dataclass
class PendingProposal:
    proposal_id: str
    plan: dict[str, Any]
    created_at: str
    max_level: int = 1


class ActionExecutor:
    """Executes planned tool actions with confirm-gate and audit trail."""

    def __init__(self, tools: dict[str, ActionFn] | None = None):
        self.tools = tools or {}
        self._pending: dict[str, PendingProposal] = {}
        # Track number of confirmations per proposal
        self._confirmations: dict[str, int] = {}
        self.audit_log: list[dict[str, Any]] = []

    def register_tool(self, name: str, handler: ActionFn) -> None:
        self.tools[name] = handler

    def confirm(self, proposal_id: str, approved: bool) -> bool:
        if not approved:
            self._pending.pop(proposal_id, None)
            self._confirmations.pop(proposal_id, None)
            return False
        
        proposal = self._pending.get(proposal_id)
        if not proposal:
            return False
            
        count = self._confirmations.get(proposal_id, 0) + 1
        self._confirmations[proposal_id] = count
        
        logger.info("proposal_confirm proposal_id=%s count=%s max_level=%s", 
                    proposal_id, count, proposal.max_level)
        return True

    def _get_max_level(self, plan: dict[str, Any]) -> int:
        from app.tools.action_registry import action_registry
        steps = plan.get("steps", [])
        max_level = 1
        for step in steps:
            tool_name = step.get("tool")
            # Lookup action definition in registry
            action_def = action_registry._actions_by_name.get(tool_name)
            if action_def:
                max_level = max(max_level, action_def.level)
            else:
                # Fallback for dynamic/unknown tools
                action_type = step.get("action_type")
                if action_type == "high_risk":
                    max_level = max(max_level, 4)
                elif action_type == "write":
                    max_level = max(max_level, 3)
        return max_level

    def _needs_confirmation(self, plan: dict[str, Any]) -> bool:
        return self._get_max_level(plan) >= 3

    def _propose(self, plan: dict[str, Any], max_level: int) -> str:
        proposal_id = f"proposal-{uuid.uuid4().hex[:12]}"
        self._pending[proposal_id] = PendingProposal(
            proposal_id=proposal_id,
            plan=plan,
            created_at=datetime.now(UTC).isoformat(),
            max_level=max_level,
        )
        self._confirmations[proposal_id] = 0
        return proposal_id

    def _audit(self, step: dict[str, Any], status: str, proposal_id: str | None) -> None:
        action_type = step.get("action_type")
        # Only audit Level 3+ (write/destructive)
        from app.tools.action_registry import action_registry
        tool_name = step.get("tool")
        action_def = action_registry._actions_by_name.get(tool_name)
        
        should_audit = (action_type in {"write", "high_risk"}) or (action_def and action_def.level >= 3)
        if not should_audit:
            return
            
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "proposal_id": proposal_id,
            "tool": tool_name,
            "action_type": action_type or (f"level_{action_def.level}" if action_def else "unknown"),
            "status": status,
            "params": step.get("params", {}),
        }
        self.audit_log.append(entry)
        logger.info("audit_entry=%s", entry)

    def _validate_step(self, step: dict[str, Any]) -> bool:
        """Validates tool parameters against the action registry schema."""
        from app.tools.action_registry import action_registry
        tool_name = step.get("tool")
        params = step.get("params", {})
        action_def = action_registry._actions_by_name.get(tool_name)
        if not action_def:
            # Fallback for dynamic tools not in registry
            return True
            
        required_fields = action_def.inputs_schema.get("required", [])
        for field in required_fields:
            if field not in params:
                logger.error("missing_required_field=%s tool=%s", field, tool_name)
                return False
        return True

    def execute_plan(self, plan: dict[str, Any], dry_run: bool = True, proposal_id: str | None = None) -> dict[str, Any]:
        max_level = self._get_max_level(plan)
        
        if max_level >= 3 and not dry_run:
            if not proposal_id:
                new_proposal_id = self._propose(plan, max_level)
                for step in plan.get("steps", []):
                    self._audit(step, "awaiting_confirmation", new_proposal_id)
                return {
                    "status": "confirmation_required",
                    "proposal_id": new_proposal_id,
                    "level": max_level,
                    "steps": plan.get("steps", []),
                }
            
            proposal = self._pending.get(proposal_id)
            if not proposal:
                return {
                    "status": "proposal_not_found",
                    "proposal_id": proposal_id,
                }
                
            confirms = self._confirmations.get(proposal_id, 0)
            required = 2 if proposal.max_level >= 4 else 1
            
            if confirms < required:
                return {
                    "status": "confirmation_missing",
                    "proposal_id": proposal_id,
                    "level": proposal.max_level,
                    "current_confirms": confirms,
                    "required_confirms": required,
                }

        results: list[dict[str, Any]] = []
        for step in plan.get("steps", []):
            tool_name = step.get("tool")
            if dry_run:
                self._audit(step, "dry_run", proposal_id)
                results.append({"tool": tool_name, "status": "dry_run", "params": step.get("params", {})})
                continue

            if not self._validate_step(step):
                self._audit(step, "validation_failed", proposal_id)
                results.append({"tool": tool_name, "status": "validation_failed"})
                continue

            handler = self.tools.get(tool_name)
            if handler is None:
                self._audit(step, "tool_not_found", proposal_id)
                results.append({"tool": tool_name, "status": "tool_not_found"})
                continue

            output = handler(step.get("params", {}))
            self._audit(step, "executed", proposal_id)
            results.append({"tool": tool_name, "status": "executed", "output": output})

        if proposal_id:
            self._pending.pop(proposal_id, None)
            self._confirmations.pop(proposal_id, None)

        return {"status": "ok", "results": results}
