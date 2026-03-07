from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from flask import Request

from app.ai.guardrails import validate_prompt
from app.auth import current_role, current_tenant, current_user
from app.errors import json_error
from app.security import confirm_gate
from app.security.gates import scan_nested_payload_for_injection
from app.tools.action_registry import action_registry

PermissionChecker = Callable[[str, str], bool]
ActionHandler = Callable[[dict[str, Any]], dict[str, Any]]

PERMISSION_TO_MIN_ROLE: dict[str, str] = {
    "read": "READONLY",
    "write": "OPERATOR",
    "admin": "ADMIN",
}

ROLE_ORDER: list[str] = ["READONLY", "OPERATOR", "ADMIN", "DEV"]


class PermissionDeniedError(RuntimeError):
    pass


class ActionValidationError(ValueError):
    pass


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


class ToolActionSharedService:
    """Shared execution pipeline for tool actions (audit/approval/guardrails/schema)."""

    @staticmethod
    def log_event(event_type: str, data: Mapping[str, Any]) -> None:
        from app.logging.structured_logger import log_event

        log_event(event_type, dict(data))

    def require_permission(self, permission: str, *, role: str | None = None) -> None:
        user_role = str(role or current_role() or "READONLY").upper()
        required = PERMISSION_TO_MIN_ROLE.get(str(permission or "read").lower(), "ADMIN")
        if user_role not in ROLE_ORDER:
            user_role = "READONLY"
        if ROLE_ORDER.index(user_role) < ROLE_ORDER.index(required):
            raise PermissionDeniedError(f"permission '{permission}' requires role '{required}'")

    def validate_input_schema(self, payload: Mapping[str, Any], schema: Mapping[str, Any]) -> None:
        required = schema.get("required") or []
        for field in required:
            if payload.get(str(field)) in (None, ""):
                raise ActionValidationError(f"{field}_missing")

        properties = schema.get("properties") or {}
        for field, raw_value in payload.items():
            spec = properties.get(field)
            if not isinstance(spec, Mapping):
                continue
            expected_type = str(spec.get("type") or "").lower()
            if expected_type == "string" and raw_value is not None and not isinstance(raw_value, str):
                raise ActionValidationError(f"{field}_invalid_type")
            if expected_type == "boolean" and not isinstance(raw_value, bool):
                raise ActionValidationError(f"{field}_invalid_type")
            enum_values = spec.get("enum")
            if isinstance(enum_values, list) and enum_values and raw_value not in enum_values:
                raise ActionValidationError(f"{field}_invalid_enum")

    def enforce_guardrails(self, payload: Mapping[str, Any]) -> None:
        finding = scan_nested_payload_for_injection(payload)
        if finding:
            raise ActionValidationError("guardrails_blocked")
        for value in payload.values():
            if isinstance(value, str):
                valid, _ = validate_prompt(value, max_len=4000)
                if not valid:
                    raise ActionValidationError("guardrails_blocked")

    def check_approval(self, *, confirm_required: bool, payload: Mapping[str, Any], req: Request) -> bool:
        if not confirm_required:
            return True
        confirm_token = payload.get("confirm") or req.headers.get("X-Confirm")
        return confirm_gate(str(confirm_token or ""))

    def load_registry_actions(self, *, tool: str) -> list[dict[str, Any]]:
        return [item for item in action_registry.list_actions() if str(item.get("tool")) == tool]

    def execute_flow(self, *, tool: str, action: ActionDefinition, payload: Mapping[str, Any], actor: str, tenant: str) -> tuple[dict[str, Any], int]:
        self.log_event(
            "tool_action_execute_requested",
            {
                "tool": tool,
                "action": action.name,
                "permission": action.permission,
                "risk": action.risk,
                "actor": actor,
                "tenant": tenant,
            },
        )

        try:
            result = action.handler(dict(payload))
        except ValueError as exc:
            self.log_event(
                "tool_action_execute_failed",
                {
                    "tool": tool,
                    "action": action.name,
                    "actor": actor,
                    "tenant": tenant,
                    "ok": False,
                    "error": str(exc),
                },
            )
            return {"ok": False, "error": str(exc), "tool": tool, "name": action.name}, 400

        self.log_event(
            "tool_action_execute_completed",
            {
                "tool": tool,
                "action": action.name,
                "actor": actor,
                "tenant": tenant,
                "ok": True,
            },
        )
        return {
            "ok": True,
            "tool": tool,
            "name": action.name,
            "result": result,
        }, 200


@dataclass
class ActionExecutionContext:
    actor: str
    tenant: str

    @classmethod
    def from_request(cls) -> "ActionExecutionContext":
        return cls(actor=str(current_user() or "system"), tenant=str(current_tenant() or "default"))


class ToolActionTemplate:
    def __init__(self, *, tool: str, actions: list[ActionDefinition], shared: ToolActionSharedService | None = None):
        self.tool = tool
        self._actions = {item.name: item for item in actions}
        self._shared = shared or ToolActionSharedService()

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
        if not items:
            for action in self._shared.load_registry_actions(tool=self.tool):
                items.append(
                    {
                        "name": str(action.get("name") or ""),
                        "title": str(action.get("name") or ""),
                        "permission": "read",
                        "risk": "low",
                        "confirm_required": bool(action.get("is_critical")),
                        "input_schema": dict(action.get("inputs_schema") or {"type": "object", "properties": {}}),
                        "output_schema": {"type": "object", "properties": {}},
                    }
                )
        return {"ok": True, "tool": self.tool, "actions": items}

    def execute(self, *, action_name: str, req: Request) -> tuple[dict[str, Any], int]:
        action = self._actions.get(action_name)
        if action is None:
            return {"ok": False, "error": "unknown_action", "tool": self.tool, "name": action_name}, 404

        try:
            self._shared.require_permission(action.permission)
        except PermissionDeniedError:
            return json_error("forbidden", "Nicht erlaubt.", status=403).get_json(), 403

        payload = req.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            payload = {}

        confirm_required = action.write_operation or action.risk == "high_risk"
        if not self._shared.check_approval(confirm_required=confirm_required, payload=payload, req=req):
            return {
                "ok": False,
                "error": "confirm_required",
                "tool": self.tool,
                "name": action.name,
            }, 409

        try:
            self._shared.validate_input_schema(payload, action.input_schema)
            self._shared.enforce_guardrails(payload)
        except ActionValidationError as exc:
            return {"ok": False, "error": str(exc), "tool": self.tool, "name": action.name}, 400

        context = ActionExecutionContext.from_request()
        return self._shared.execute_flow(tool=self.tool, action=action, payload=payload, actor=context.actor, tenant=context.tenant)
