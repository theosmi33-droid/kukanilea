from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.tools.action_registry import action_registry


@dataclass
class WorkflowStep:
    action: str
    params: Dict[str, Any] = field(default_factory=dict)
    emit_event: Optional[str] = None


class ActionManager:
    """Manager agent helper for listing, searching and composing action workflows."""

    def list_actions(self) -> List[Dict[str, Any]]:
        return action_registry.list_actions()

    def search_actions(
        self,
        query: str = "",
        *,
        critical_only: bool = False,
        permissions: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        return action_registry.search(
            query,
            critical_only=critical_only,
            permissions=permissions or [],
        )

    def compose_workflow(self, steps: List[Dict[str, Any]]) -> Dict[str, Any]:
        action_names = {item["name"] for item in action_registry.list_actions()}
        workflow_steps: List[WorkflowStep] = []
        events: List[Dict[str, Any]] = []

        for idx, raw_step in enumerate(steps):
            action = str(raw_step.get("action") or "").strip()
            if not action:
                raise ValueError(f"workflow_step_{idx}_missing_action")
            if action not in action_names:
                raise ValueError(f"workflow_step_{idx}_unknown_action:{action}")

            step = WorkflowStep(
                action=action,
                params=dict(raw_step.get("params") or {}),
                emit_event=(str(raw_step.get("emit_event")).strip() if raw_step.get("emit_event") else None),
            )
            workflow_steps.append(step)
            if step.emit_event:
                events.append(
                    {
                        "type": step.emit_event,
                        "source_action": step.action,
                        "step_index": idx,
                    }
                )

        return {
            "workflow": [
                {
                    "action": step.action,
                    "params": step.params,
                    "emit_event": step.emit_event,
                }
                for step in workflow_steps
            ],
            "events": events,
            "action_count": len(workflow_steps),
        }
