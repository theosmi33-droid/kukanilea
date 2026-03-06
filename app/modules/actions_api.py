from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from flask import Request, jsonify, request

from app.auth import current_role, current_tenant, current_user, login_required
from app.errors import json_error
from app.security.approval_runtime import RuntimeApprovalPolicy, create_approval_challenge, validate_approval_token


PermissionChecker = Callable[[str, str], bool]
ActionHandler = Callable[[dict[str, Any]], dict[str, Any]]


PERMISSION_TO_MIN_ROLE: dict[str, str] = {
    "read": "READONLY",
    "write": "OPERATOR",
    "admin": "ADMIN",
}

ROLE_ORDER: list[str] = ["READONLY", "OPERATOR", "ADMIN", "DEV"]


class SharedServices:
    """Small façade for cross-cutting helpers used by actions endpoints."""

    @staticmethod
    def log_event(event_type: str, data: Mapping[str, Any]) -> None:
        from app.logging.structured_logger import log_event

        log_event(event_type, dict(data))


class PermissionDeniedError(RuntimeError):
    pass


def require_permission(permission: str, *, role: str | None = None) -> None:
    user_role = str(role or current_role() or "READONLY").upper()
    required = PERMISSION_TO_MIN_ROLE.get(str(permission or "read").lower(), "ADMIN")
    if user_role not in ROLE_ORDER:
        user_role = "READONLY"
    if ROLE_ORDER.index(user_role) < ROLE_ORDER.index(required):
        raise PermissionDeniedError(f"permission '{permission}' requires role '{required}'")


@dataclass(frozen=True)
class ActionDefinition:
    name: str
    title: str
    permission: str
    risk: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    handler: ActionHandler

    @property
    def write_operation(self) -> bool:
        return self.permission.lower() == "write"


class ActionApiTemplate:
    def __init__(self, *, tool: str, actions: list[ActionDefinition]):
        self.tool = tool
        self._actions = {item.name: item for item in actions}

    def list_actions_payload(self) -> dict[str, Any]:
        items: list[dict[str, Any]] = []
        for action in self._actions.values():
            items.append(
                {
                    "name": action.name,
                    "title": action.title,
                    "permission": action.permission,
                    "risk": action.risk,
                    "confirm_required": action.write_operation or action.risk == "high_risk",
                    "input_schema": action.input_schema,
                    "output_schema": action.output_schema,
                }
            )
        return {"ok": True, "tool": self.tool, "actions": items}

    def execute(self, *, action_name: str, req: Request) -> tuple[dict[str, Any], int]:
        action = self._actions.get(action_name)
        if action is None:
            return {"ok": False, "error": "unknown_action", "tool": self.tool, "name": action_name}, 404

        try:
            require_permission(action.permission)
        except PermissionDeniedError:
            return json_error("forbidden", "Nicht erlaubt.", status=403).get_json(), 403

        payload = req.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            payload = {}

        actor = str(current_user() or "system")
        tenant = str(current_tenant() or "default")
        policy = RuntimeApprovalPolicy(
            requires_confirm=bool(action.write_operation or action.risk == "high_risk"),
            risk_level=str(action.risk or "low_risk"),
            approval_scope=f"tool:{self.tool}:{action.name}",
            approval_ttl_seconds=120,
            approval_subject=f"{tenant}:{actor}",
        )

        approved, reason = validate_approval_token(
            approval_token=payload.get("approval_token") or payload.get("confirm") or req.headers.get("X-Approval-Token"),
            policy=policy,
        )
        if not approved and policy.requires_confirm:
            challenge = create_approval_challenge(policy)
            SharedServices.log_event(
                "tool_action_approval_denied",
                {
                    "tool": self.tool,
                    "action": action.name,
                    "actor": actor,
                    "tenant": tenant,
                    "approval_reason": reason,
                    "approval_scope": policy.approval_scope,
                },
            )
            return {
                "ok": False,
                "error": "confirm_required",
                "tool": self.tool,
                "name": action.name,
                "approval": {
                    "reason": reason,
                    "scope": policy.approval_scope,
                    "risk_level": policy.risk_level,
                    "approval_ttl_seconds": policy.approval_ttl_seconds,
                    "approval_subject": policy.approval_subject,
                    "challenge": challenge,
                },
            }, 409

        SharedServices.log_event(
            "tool_action_execute_requested",
            {
                "tool": self.tool,
                "action": action.name,
                "permission": action.permission,
                "risk": action.risk,
                "actor": actor,
                "tenant": tenant,
                "requires_confirm": policy.requires_confirm,
                "approval_scope": policy.approval_scope,
            },
        )

        try:
            result = action.handler(payload)
        except ValueError as exc:
            SharedServices.log_event(
                "tool_action_execute_failed",
                {
                    "tool": self.tool,
                    "action": action.name,
                    "actor": actor,
                    "tenant": tenant,
                    "ok": False,
                    "error": str(exc),
                },
            )
            return {"ok": False, "error": str(exc), "tool": self.tool, "name": action.name}, 400

        SharedServices.log_event(
            "tool_action_execute_completed",
            {
                "tool": self.tool,
                "action": action.name,
                "actor": actor,
                "tenant": tenant,
                "ok": True,
            },
        )
        return {
            "ok": True,
            "tool": self.tool,
            "name": action.name,
            "result": result,
        }, 200


def register_actions_endpoints(bp, templates: Mapping[str, ActionApiTemplate]) -> None:
    @bp.get("/api/<tool>/actions")
    @login_required
    def api_tool_actions(tool: str):
        template = templates.get(tool)
        if template is None:
            return jsonify(error="unknown_tool", tool=tool), 404
        return jsonify(template.list_actions_payload())

    @bp.post("/api/<tool>/actions/<name>")
    @login_required
    def api_tool_action_execute(tool: str, name: str):
        template = templates.get(tool)
        if template is None:
            return jsonify(error="unknown_tool", tool=tool), 404
        payload, status = template.execute(action_name=name, req=request)
        return jsonify(payload), status
