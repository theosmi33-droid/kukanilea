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


class ActionExecutor:
    """Executes planned tool actions with confirm-gate and audit trail."""

    def __init__(self, tools: dict[str, ActionFn] | None = None):
        self.tools = tools or {}
        self._pending: dict[str, PendingProposal] = {}
        self._confirmed: set[str] = set()
        self.audit_log: list[dict[str, Any]] = []

    def register_tool(self, name: str, handler: ActionFn) -> None:
        self.tools[name] = handler

    def confirm(self, proposal_id: str, approved: bool) -> bool:
        if not approved:
            self._pending.pop(proposal_id, None)
            self._confirmed.discard(proposal_id)
            return False
        if proposal_id not in self._pending:
            return False
        self._confirmed.add(proposal_id)
        return True

    def _needs_confirmation(self, plan: dict[str, Any]) -> bool:
        steps = plan.get("steps", [])
        return any(step.get("action_type") in {"write", "high_risk"} for step in steps)

    def _propose(self, plan: dict[str, Any]) -> str:
        proposal_id = f"proposal-{uuid.uuid4().hex[:12]}"
        self._pending[proposal_id] = PendingProposal(
            proposal_id=proposal_id,
            plan=plan,
            created_at=datetime.now(UTC).isoformat(),
        )
        return proposal_id

    def _audit(self, step: dict[str, Any], status: str, proposal_id: str | None) -> None:
        action_type = step.get("action_type")
        if action_type not in {"write", "high_risk"}:
            return
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "proposal_id": proposal_id,
            "tool": step.get("tool"),
            "action_type": action_type,
            "status": status,
            "params": step.get("params", {}),
        }
        self.audit_log.append(entry)
        logger.info("audit_entry=%s", entry)

    def execute_plan(self, plan: dict[str, Any], dry_run: bool = True, proposal_id: str | None = None) -> dict[str, Any]:
        if self._needs_confirmation(plan) and not dry_run:
            if not proposal_id:
                new_proposal_id = self._propose(plan)
                for step in plan.get("steps", []):
                    self._audit(step, "awaiting_confirmation", new_proposal_id)
                return {
                    "status": "confirmation_required",
                    "proposal_id": new_proposal_id,
                    "steps": plan.get("steps", []),
                }
            if proposal_id not in self._confirmed:
                return {
                    "status": "confirmation_missing",
                    "proposal_id": proposal_id,
                }

        results: list[dict[str, Any]] = []
        for step in plan.get("steps", []):
            tool_name = step.get("tool")
            if dry_run:
                self._audit(step, "dry_run", proposal_id)
                results.append({"tool": tool_name, "status": "dry_run", "params": step.get("params", {})})
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
            self._confirmed.discard(proposal_id)

        return {"status": "ok", "results": results}
