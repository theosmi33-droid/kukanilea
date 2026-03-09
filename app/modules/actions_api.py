from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Callable, Mapping

from flask import Request, jsonify, request

from app.auth import current_role, current_tenant, current_user, login_required
from app.errors import json_error
from app.security import (
    ApprovalEngine,
    ApprovalScope,
    action_requires_approval,
    build_params_fingerprint,
    confirm_gate,
)
from kukanilea.idempotency import GLOBAL_IDEMPOTENCY_STORE, canonical_hash

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


_APPROVAL_ENGINE: ApprovalEngine | None = None


def _approval_engine() -> ApprovalEngine:
    global _APPROVAL_ENGINE
    if _APPROVAL_ENGINE is None:
        _APPROVAL_ENGINE = ApprovalEngine(audit_hook=SharedServices.log_event)
    return _APPROVAL_ENGINE


def _build_scope(*, tool: str, action_name: str, tenant: str, user: str, payload: dict[str, Any]) -> ApprovalScope:
    return ApprovalScope(
        tenant_id=tenant,
        user_id=user,
        action_id=f"{tool}.{action_name}",
        params_fingerprint=build_params_fingerprint(payload),
    )


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
    IDEMPOTENCY_TTL_SECONDS = 24 * 60 * 60
    WRITE_DEDUP_WINDOW_SECONDS = 15
    APPROVAL_TTL_SECONDS = 300
    APPROVAL_TTL_MAX_SECONDS = 600

    def __init__(self, *, tool: str, actions: list[ActionDefinition]):
        self.tool = tool
        self._actions = {item.name: item for item in actions}

    @staticmethod
    def _request_hash(payload: Mapping[str, Any]) -> str:
        normalized = {
            key: value
            for key, value in payload.items()
            if key not in {"confirm", "approval_token", "approval_ttl", "idempotency_key", "request_id", "phase", "meta"}
        }
        return canonical_hash(normalized)

    def _resolve_idempotency_key(self, req: Request, payload: Mapping[str, Any], request_hash: str) -> tuple[str, int, str]:
        explicit = str(req.headers.get("Idempotency-Key") or payload.get("idempotency_key") or "").strip()
        if explicit:
            return explicit, self.IDEMPOTENCY_TTL_SECONDS, "explicit"
        derived = sha256(f"{self.tool}:{request_hash}".encode("utf-8")).hexdigest()[:32]
        return f"dedup:{derived}", self.WRITE_DEDUP_WINDOW_SECONDS, "derived"

    def _resolve_approval_ttl(self, payload: Mapping[str, Any]) -> int:
        raw = payload.get("approval_ttl")
        try:
            ttl = int(raw) if raw is not None else self.APPROVAL_TTL_SECONDS
        except (TypeError, ValueError):
            ttl = self.APPROVAL_TTL_SECONDS
        return max(1, min(ttl, self.APPROVAL_TTL_MAX_SECONDS))

    def list_actions_payload(self) -> dict[str, Any]:
        items: list[dict[str, Any]] = []
        for action in self._actions.values():
            approval_required = action_requires_approval(
                action_type=action.name,
                permission=action.permission,
                risk=action.risk,
            )
            items.append(
                {
                    "name": action.name,
                    "title": action.title,
                    "permission": action.permission,
                    "risk": action.risk,
                    "confirm_required": approval_required,
                    "approval_required": approval_required,
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
            response, status = json_error("forbidden", "Nicht erlaubt.", status=403)
            return response.get_json(), status

        payload = req.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            payload = {}

        actor = str(current_user() or "system")
        tenant = str(current_tenant() or "default")

        # Never trust tenant hints from callers. Tool actions always execute in the
        # authenticated session tenant.
        handler_payload = dict(payload)
        handler_payload.pop("tenant_id", None)
        handler_payload.pop("tenant", None)
        handler_payload.pop("tenantId", None)
        handler_payload["tenant_id"] = tenant

        request_hash = self._request_hash(handler_payload)
        idempotency_key = ""
        idem_scope = ""
        idem_token = ""
        idempotency_mode = "none"
        if action.write_operation:
            idempotency_key, idem_ttl, idempotency_mode = self._resolve_idempotency_key(req, handler_payload, request_hash)
            idem_scope = f"{tenant}:{self.tool}:{action.name}"
            decision = GLOBAL_IDEMPOTENCY_STORE.begin(
                scope=idem_scope,
                key=idempotency_key,
                request_hash=request_hash,
                ttl_seconds=idem_ttl,
            )
            SharedServices.log_event(
                "tool_action_idempotency_checked",
                {
                    "tool": self.tool,
                    "action": action.name,
                    "actor": actor,
                    "tenant": tenant,
                    "idempotency_key": idempotency_key,
                    "idempotency_mode": idempotency_mode,
                    "idempotency_status": decision.status,
                },
            )

            if decision.status == "conflict":
                return {
                    "ok": False,
                    "error": "idempotency_conflict",
                    "tool": self.tool,
                    "name": action.name,
                }, 409
            if decision.status == "in_flight":
                return {
                    "ok": False,
                    "error": "idempotency_in_flight",
                    "tool": self.tool,
                    "name": action.name,
                }, 409
            if decision.status == "replay":
                replay_payload = dict(decision.response or {})
                replay_payload.update(
                    {
                        "ok": True,
                        "tool": self.tool,
                        "name": action.name,
                        "idempotent_replay": True,
                    }
                )
                return replay_payload, int(decision.status_code or 200)
            idem_token = str(decision.token or "")

        approval_required = action_requires_approval(
            action_type=action.name,
            permission=action.permission,
            risk=action.risk,
        )
        if approval_required:
            scope = _build_scope(tool=self.tool, action_name=action.name, tenant=tenant, user=actor, payload=handler_payload)
            approval_token = handler_payload.get("approval_token") or req.headers.get("X-Approval-Token")

            # Backward-compatible gate: allow legacy explicit confirm tokens while migrating to challenge-based approvals.
            if not approval_token:
                legacy_confirm = handler_payload.get("confirm") or req.headers.get("X-Confirm")
                if confirm_gate(str(legacy_confirm or "")):
                    SharedServices.log_event(
                        "tool_action_approval_legacy_confirm",
                        {
                            "tool": self.tool,
                            "action": action.name,
                            "actor": actor,
                            "tenant": tenant,
                            "idempotency_key": idempotency_key or None,
                            "idempotency_mode": idempotency_mode,
                        },
                    )
                    approval_token = None

            if approval_token:
                approved, reason = _approval_engine().validate(token=str(approval_token), scope=scope)
                if not approved:
                    if idem_token:
                        GLOBAL_IDEMPOTENCY_STORE.complete_failure(scope=idem_scope, key=idempotency_key, token=idem_token)
                    return {
                        "ok": False,
                        "error": "approval_required",
                        "approval_reason": reason,
                        "tool": self.tool,
                        "name": action.name,
                    }, 409
            elif not confirm_gate(str(handler_payload.get("confirm") or req.headers.get("X-Confirm") or "")):
                if idem_token:
                    GLOBAL_IDEMPOTENCY_STORE.complete_failure(scope=idem_scope, key=idempotency_key, token=idem_token)
                ttl_seconds = self._resolve_approval_ttl(handler_payload)
                challenge = _approval_engine().request_challenge(scope=scope, ttl_seconds=ttl_seconds)
                return {
                    "ok": False,
                    "error": "approval_required",
                    "tool": self.tool,
                    "name": action.name,
                    "approval": {
                        "challenge_id": challenge.challenge_id,
                        "approval_token": challenge.token,
                        "scope": {
                            "tenant_id": scope.tenant_id,
                            "user_id": scope.user_id,
                            "action_id": scope.action_id,
                            "params_fingerprint": scope.params_fingerprint,
                        },
                        "expires_at": challenge.expires_at.isoformat(),
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
            },
        )

        try:
            result = action.handler(handler_payload)
        except ValueError as exc:
            if idem_token:
                GLOBAL_IDEMPOTENCY_STORE.complete_failure(scope=idem_scope, key=idempotency_key, token=idem_token)
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
        except Exception:
            if idem_token:
                GLOBAL_IDEMPOTENCY_STORE.complete_failure(scope=idem_scope, key=idempotency_key, token=idem_token)
            SharedServices.log_event(
                "tool_action_execute_failed",
                {
                    "tool": self.tool,
                    "action": action.name,
                    "actor": actor,
                    "tenant": tenant,
                    "ok": False,
                    "error": "unexpected_error",
                },
            )
            return {"ok": False, "error": "unexpected_error", "tool": self.tool, "name": action.name}, 500

        response = {
            "ok": True,
            "tool": self.tool,
            "name": action.name,
            "result": result,
        }
        if action.write_operation and idem_token:
            GLOBAL_IDEMPOTENCY_STORE.complete_success(
                scope=idem_scope,
                key=idempotency_key,
                token=idem_token,
                response=response,
                status_code=200,
                ttl_seconds=idem_ttl,
            )

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
        return response, 200


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
