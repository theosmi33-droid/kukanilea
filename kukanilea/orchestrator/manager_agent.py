from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from os import getenv
from typing import Any, Callable, Mapping

from .action_catalog import create_action_registry
from .action_registry import ActionRegistry
from .approval_runtime import ApprovalRuntime

INJECTION_PATTERNS = (
    re.compile(r"\bignore\s+previous\s+instructions\b", re.IGNORECASE),
    re.compile(r"\bignore\s+all\s+instructions\b", re.IGNORECASE),
    re.compile(r"\bsystem\s+prompt\b", re.IGNORECASE),
    re.compile(r"\bdeveloper\s+message\b", re.IGNORECASE),
    re.compile(r"\bbypass\s+(policy|safety|confirm)\b", re.IGNORECASE),
)

RUNTIME_REVIEW_PATTERNS = (
    re.compile(r"\b(delete\s+files?|rm\s+-rf|drop\s+table)\b", re.IGNORECASE),
    re.compile(r"\b(exfiltrat\w*|export\s+(all\s+)?data|leak\s+data)\b", re.IGNORECASE),
)

RUNTIME_WARNING_PATTERNS = (
    re.compile(r"\b(ignore\s+previous\s+instructions?)\b", re.IGNORECASE),
    re.compile(r"\b(bypass\s+(policy|safety|guardrails?))\b", re.IGNORECASE),
    re.compile(r"\b(reveal|show)\s+(the\s+)?system\s+prompt\b", re.IGNORECASE),
)


class GuardDecision(str, Enum):
    ALLOW = "allow"
    ALLOW_WITH_WARNING = "allow_with_warning"
    BLOCK = "block"
    ROUTE_TO_REVIEW = "route_to_review"


@dataclass(frozen=True)
class RuntimeGuardResult:
    decision: GuardDecision
    reasons: list[str] = field(default_factory=list)
    normalized_message: str = ""
    stage: str = ""


@dataclass(frozen=True)
class IntentSpec:
    name: str
    patterns: tuple[re.Pattern[str], ...]
    candidate_actions: tuple[str, ...]
    required_entities: tuple[str, ...] = ()


@dataclass(frozen=True)
class MIAIntentPlan:
    intent_name: str
    confidence: float
    candidate_actions: list[str]
    required_entities: list[str]
    missing_context: list[str]
    risk_assessment: str
    execution_mode: str  # read, propose, confirm, execute


@dataclass(frozen=True)
class RouteDecision:
    intent: str
    tool: str
    action: str
    requires_confirm: bool = False
    external_call: bool = False
    execution_mode: str = "read"


@dataclass
class RouteResult:
    ok: bool
    status: str
    decision: RouteDecision
    reason: str = ""
    confirm_required: bool = False
    plan: MIAIntentPlan | None = None
    audit_event: dict[str, Any] | None = None


@dataclass(frozen=True)
class ExternalCallPolicyDecision:
    allowed: bool
    reason: str
    action_allowlisted: bool


class ExternalCallPolicy:
    """Offline-first policy for external API actions.

    Default behavior blocks external calls unless `external_calls_enabled` is true
    and the canonical action id is explicitly allowlisted.
    """

    def __init__(
        self,
        *,
        external_calls_enabled: bool,
        allowlisted_actions: tuple[str, ...] = (),
    ) -> None:
        self.external_calls_enabled = bool(external_calls_enabled)
        self.allowlisted_actions = {str(action).strip() for action in allowlisted_actions if str(action).strip()}

    @classmethod
    def from_env(cls, *, external_calls_enabled: bool) -> "ExternalCallPolicy":
        raw = str(getenv("KUKANILEA_EXTERNAL_CALL_ALLOWLIST", "")).strip()
        entries = tuple(segment.strip() for segment in raw.split(",") if segment.strip())
        return cls(external_calls_enabled=external_calls_enabled, allowlisted_actions=entries)

    def evaluate(self, *, action_id: str, external_call: bool) -> ExternalCallPolicyDecision:
        if not external_call:
            return ExternalCallPolicyDecision(allowed=True, reason="not_external", action_allowlisted=False)
        if not self.external_calls_enabled:
            return ExternalCallPolicyDecision(allowed=False, reason="external_calls_disabled", action_allowlisted=False)
        is_allowlisted = action_id in self.allowlisted_actions
        if not is_allowlisted:
            return ExternalCallPolicyDecision(allowed=False, reason="external_action_not_allowlisted", action_allowlisted=False)
        return ExternalCallPolicyDecision(allowed=True, reason="external_action_allowlisted", action_allowlisted=True)


@dataclass
class EventBus:
    """Minimal EventBus abstraction for orchestrator events."""

    emitter: Callable[[str, dict[str, Any]], None] | None = None
    events: list[dict[str, Any]] = field(default_factory=list)

    def emit(self, event_type: str, payload: dict[str, Any]) -> None:
        event = {
            "ts": datetime.now(UTC).isoformat(timespec="seconds"),
            "event_type": str(event_type or "unknown"),
            "payload": dict(payload or {}),
        }
        self.events.append(event)
        if callable(self.emitter):
            self.emitter(event["event_type"], event["payload"])


class DeterministicToolRouter:
    """Deterministic MIA intent detector and action router for local workflows."""

    def __init__(self, action_registry: ActionRegistry | None = None) -> None:
        self.action_registry = action_registry or create_action_registry()

    INTENT_LIBRARY: tuple[IntentSpec, ...] = (
        IntentSpec(
            name="dashboard_status",
            patterns=(
                re.compile(r"\b(dashboard|status|health|übersicht)\b", re.IGNORECASE),
            ),
            candidate_actions=("dashboard.summary.read",),
        ),
        IntentSpec(
            name="customer_lookup",
            patterns=(
                re.compile(r"\b(kunde|kundennummer|kdnr|wer\s+ist)\b", re.IGNORECASE),
            ),
            candidate_actions=("crm.customer.search",),
            required_entities=("customer_id",),
        ),
        IntentSpec(
            name="task_management",
            patterns=(
                re.compile(r"\b(aufgabe|task|todo|einsatz)\b", re.IGNORECASE),
            ),
            candidate_actions=("tasks.task.create",),
            required_entities=("title",),
        ),
        IntentSpec(
            name="appointment_planning",
            patterns=(
                re.compile(r"\b(termin|kalender|baustelle\s+einplanen)\b", re.IGNORECASE),
            ),
            candidate_actions=("calendar.appointment.create",),
            required_entities=("date", "summary"),
        ),
        IntentSpec(
            name="invoice_search",
            patterns=(
                re.compile(r"\b(rechnung|angebot|lieferschein|beleg)\b", re.IGNORECASE),
            ),
            candidate_actions=("dms.invoice.search",),
        ),
        IntentSpec(
            name="document_search",
            patterns=(
                re.compile(r"\b(dokument|vertrag|akte|archiv|dms)\b", re.IGNORECASE),
            ),
            candidate_actions=("dms.document.search",),
        ),
        IntentSpec(
            name="material_check",
            patterns=(
                re.compile(r"\b(material|lager|bestand)\b", re.IGNORECASE),
            ),
            candidate_actions=("warehouse.material.status",),
        ),
        IntentSpec(
            name="supplier_lookup",
            patterns=(
                re.compile(r"\b(lieferant\w*|supplier|bezugsquelle)\b", re.IGNORECASE),
            ),
            candidate_actions=("warehouse.supplier.search",),
        ),
        IntentSpec(
            name="mail_response",
            patterns=(
                re.compile(r"\b(mail|email|e-mail)\b.*\b(antworte|antworten|reply|senden)\b|\b(antworte|antworten|reply|senden)\b.*\b(mail|email|e-mail)\b", re.IGNORECASE),
            ),
            candidate_actions=("mail.mail.reply",),
            required_entities=("message",),
        ),
        IntentSpec(
            name="mail_search",
            patterns=(
                re.compile(r"\b(mail|email|e-mail|postfach|inbox)\b", re.IGNORECASE),
            ),
            candidate_actions=("mail.inbox.search",),
        ),
        IntentSpec(
            name="messenger_response",
            patterns=(
                re.compile(r"\b(nachricht|messenger|antworten|whatsapp|telegram)\b", re.IGNORECASE),
            ),
            candidate_actions=("messenger.message.reply",),
            required_entities=("message",),
        ),
    )

    SAFE_SUGGESTIONS = (
        "Möchtest du den Dashboard-Status sehen?",
        "Soll ich eine Kundeninfo anhand der Kundennummer suchen?",
        "Ich kann eine Aufgabe vorbereiten, wenn du Titel und Termin nennst.",
    )

    def contains_injection(self, message: str) -> tuple[bool, list[str]]:
        text = str(message or "")
        matches = [pattern.pattern for pattern in INJECTION_PATTERNS if pattern.search(text)]
        return bool(matches), matches

    def normalize_untrusted_input(self, message: str) -> str:
        text = str(message or "")
        return re.sub(r"\s+", " ", text).strip()

    def assess_runtime_guard(self, message: str, *, stage: str) -> RuntimeGuardResult:
        normalized = self.normalize_untrusted_input(message)
        injection_matches = [pattern.pattern for pattern in INJECTION_PATTERNS if pattern.search(normalized)]
        review_matches = [pattern.pattern for pattern in RUNTIME_REVIEW_PATTERNS if pattern.search(normalized)]
        warning_matches = [pattern.pattern for pattern in RUNTIME_WARNING_PATTERNS if pattern.search(normalized)]

        if injection_matches:
            return RuntimeGuardResult(
                decision=GuardDecision.BLOCK,
                reasons=injection_matches,
                normalized_message=normalized,
                stage=stage,
            )
        if review_matches:
            return RuntimeGuardResult(
                decision=GuardDecision.ROUTE_TO_REVIEW,
                reasons=review_matches,
                normalized_message=normalized,
                stage=stage,
            )
        if warning_matches:
            return RuntimeGuardResult(
                decision=GuardDecision.ALLOW_WITH_WARNING,
                reasons=warning_matches,
                normalized_message=normalized,
                stage=stage,
            )
        return RuntimeGuardResult(
            decision=GuardDecision.ALLOW,
            reasons=[],
            normalized_message=normalized,
            stage=stage,
        )

    def build_plan(self, message: str) -> MIAIntentPlan:
        text = str(message or "").strip()
        if not text:
            return MIAIntentPlan(
                intent_name="unknown",
                confidence=0.0,
                candidate_actions=[],
                required_entities=[],
                missing_context=["request"],
                risk_assessment="low",
                execution_mode="propose",
            )

        for spec in self.INTENT_LIBRARY:
            if any(pattern.search(text) for pattern in spec.patterns):
                missing = [entity for entity in spec.required_entities if not self._entity_present(entity, text)]
                action_specs = [self.action_registry.actions[name] for name in spec.candidate_actions if name in self.action_registry.actions]
                highest_risk = "low"
                if any(action.policy.external_call for action in action_specs):
                    highest_risk = "high"
                elif any(action.policy.confirm_required for action in action_specs):
                    highest_risk = "medium"

                if missing:
                    mode = "propose"
                elif any(action.policy.confirm_required for action in action_specs):
                    mode = "confirm"
                else:
                    mode = "read"

                return MIAIntentPlan(
                    intent_name=spec.name,
                    confidence=0.92 if not missing else 0.74,
                    candidate_actions=list(spec.candidate_actions),
                    required_entities=list(spec.required_entities),
                    missing_context=missing,
                    risk_assessment=highest_risk,
                    execution_mode=mode,
                )

        return MIAIntentPlan(
            intent_name="unknown",
            confidence=0.2,
            candidate_actions=[],
            required_entities=[],
            missing_context=["intent_clarification"],
            risk_assessment="low",
            execution_mode="propose",
        )

    def select(self, plan: MIAIntentPlan) -> RouteDecision:
        action_name = next((action for action in plan.candidate_actions if action in self.action_registry.actions), "")
        if not action_name:
            return RouteDecision(
                intent=plan.intent_name,
                tool="chatbot",
                action="safe_follow_up",
                execution_mode="propose",
            )

        spec = self.action_registry.actions[action_name]
        mode = plan.execution_mode
        if plan.missing_context:
            mode = "propose"
        return RouteDecision(
            intent=plan.intent_name,
            tool=spec.tool,
            action=spec.action_id,
            requires_confirm=spec.policy.confirm_required,
            external_call=spec.policy.external_call,
            execution_mode=mode,
        )

    def validate_parameters(self, action: str, params: Mapping[str, Any] | None) -> bool:
        spec = self.action_registry.actions.get(action)
        if not spec:
            return False
        provided = dict(params or {})
        if not provided:
            return True
        allowed = set(spec.parameter_schema.keys())
        return set(provided.keys()).issubset(allowed)

    def _entity_present(self, entity: str, text: str) -> bool:
        checks = {
            "customer_id": bool(re.search(r"\b\d{3,}\b", text)),
            "title": len(text.split()) >= 3,
            "date": bool(re.search(r"\b\d{1,2}[.\-/]\d{1,2}([.\-/]\d{2,4})?\b", text)),
            "summary": len(text.split()) >= 4,
            "message": len(text.split()) >= 4,
        }
        return checks.get(entity, False)


class ManagerAgent:
    def __init__(
        self,
        *,
        event_bus: EventBus | None = None,
        audit_logger: Callable[[dict[str, Any]], None] | None = None,
        external_calls_enabled: bool = False,
        external_call_allowlist: tuple[str, ...] | None = None,
        approval_runtime: ApprovalRuntime | None = None,
    ) -> None:
        self.router = DeterministicToolRouter()
        self.event_bus = event_bus or EventBus()
        self.audit_logger = audit_logger
        self.external_calls_enabled = bool(external_calls_enabled)
        if external_call_allowlist is None:
            self.external_call_policy = ExternalCallPolicy.from_env(external_calls_enabled=self.external_calls_enabled)
        else:
            self.external_call_policy = ExternalCallPolicy(
                external_calls_enabled=self.external_calls_enabled,
                allowlisted_actions=tuple(external_call_allowlist),
            )
        self.approvals = approval_runtime or ApprovalRuntime(audit_logger=self._record_approval_event)

    def route(self, message: str, context: Mapping[str, Any] | None = None) -> RouteResult:
        ctx = dict(context or {})

        pre_guard = self.router.assess_runtime_guard(message, stage="pre_intent")
        if pre_guard.decision == GuardDecision.BLOCK:
            blocked_plan = MIAIntentPlan(
                intent_name="security_blocked",
                confidence=1.0,
                candidate_actions=[],
                required_entities=[],
                missing_context=[],
                risk_assessment="high",
                execution_mode="propose",
            )
            decision = RouteDecision(intent="security_blocked", tool="chatbot", action="safe_fallback", execution_mode="propose")
            result = RouteResult(
                ok=False,
                status="blocked",
                decision=decision,
                reason="prompt_injection",
                plan=blocked_plan,
            )
            self._record(
                "manager_agent.blocked",
                message,
                ctx,
                result,
                extra={
                    "guard_decision": pre_guard.decision.value,
                    "guard_stage": pre_guard.stage,
                    "patterns": pre_guard.reasons,
                    "suggestions": list(self.router.SAFE_SUGGESTIONS),
                },
            )
            return result

        if pre_guard.decision == GuardDecision.ROUTE_TO_REVIEW:
            review_plan = MIAIntentPlan(
                intent_name="security_review",
                confidence=1.0,
                candidate_actions=[],
                required_entities=[],
                missing_context=[],
                risk_assessment="high",
                execution_mode="propose",
            )
            decision = RouteDecision(intent="security_review", tool="chatbot", action="safe_fallback", execution_mode="propose")
            result = RouteResult(
                ok=False,
                status="needs_review",
                decision=decision,
                reason="security_review_required",
                plan=review_plan,
            )
            self._record(
                "manager_agent.review_required",
                message,
                ctx,
                result,
                extra={
                    "guard_decision": pre_guard.decision.value,
                    "guard_stage": pre_guard.stage,
                    "patterns": pre_guard.reasons,
                    "suggestions": list(self.router.SAFE_SUGGESTIONS),
                },
            )
            return result

        if pre_guard.decision == GuardDecision.ALLOW_WITH_WARNING:
            ctx.setdefault("guard_warnings", []).extend(pre_guard.reasons)

        plan = self.router.build_plan(pre_guard.normalized_message)
        decision = self.router.select(plan)

        if decision.action not in self.router.action_registry.actions and decision.action not in {"safe_follow_up", "safe_fallback"}:
            result = RouteResult(ok=False, status="blocked", decision=decision, reason="action_not_registered", plan=plan)
            self._record("manager_agent.blocked", message, ctx, result)
            return result

        if decision.action not in {"safe_follow_up", "safe_fallback"} and (
            plan.missing_context or plan.execution_mode == "propose"
        ):
            result = RouteResult(
                ok=False,
                status="needs_clarification",
                decision=decision,
                reason="missing_context",
                plan=plan,
            )
            self._record(
                "manager_agent.needs_clarification",
                message,
                ctx,
                result,
                extra={
                    "missing_context": list(plan.missing_context),
                    "suggestions": list(self.router.SAFE_SUGGESTIONS),
                },
            )
            return result

        if plan.candidate_actions and not self.router.validate_parameters(decision.action, ctx.get("params")):
            result = RouteResult(ok=False, status="blocked", decision=decision, reason="schema_validation_failed", plan=plan)
            self._record("manager_agent.blocked", message, ctx, result)
            return result

        pre_exec_guard = self.router.assess_runtime_guard(pre_guard.normalized_message, stage="pre_execution")
        if pre_exec_guard.decision == GuardDecision.BLOCK:
            result = RouteResult(ok=False, status="blocked", decision=decision, reason="runtime_security_blocked", plan=plan)
            self._record(
                "manager_agent.blocked",
                message,
                ctx,
                result,
                extra={
                    "guard_decision": pre_exec_guard.decision.value,
                    "guard_stage": pre_exec_guard.stage,
                    "patterns": pre_exec_guard.reasons,
                },
            )
            return result

        if pre_exec_guard.decision == GuardDecision.ROUTE_TO_REVIEW:
            result = RouteResult(ok=False, status="needs_review", decision=decision, reason="runtime_review_required", plan=plan)
            self._record(
                "manager_agent.review_required",
                message,
                ctx,
                result,
                extra={
                    "guard_decision": pre_exec_guard.decision.value,
                    "guard_stage": pre_exec_guard.stage,
                    "patterns": pre_exec_guard.reasons,
                },
            )
            return result

        if decision.requires_confirm or plan.execution_mode == "confirm":
            approval = self.approvals.evaluate(
                approval_id=ctx.get("approval_id"),
                tenant=str(ctx.get("tenant") or "default"),
                user=str(ctx.get("user") or "system"),
                action_id=decision.action,
                scope=self._approval_scope(decision),
                params=ctx.get("params"),
            )
        else:
            approval = None

        if approval and not approval.allowed:
            approval_state = self._approval_state_from_reason(approval.reason)
            status = "confirm_required" if approval_state in {"confirm_required", "pending"} else "blocked"
            result = RouteResult(
                ok=False,
                status=status,
                decision=decision,
                reason=approval.reason,
                confirm_required=True,
                plan=plan,
            )
            self._record(
                "manager_agent.confirm_blocked",
                message,
                ctx,
                result,
                extra={
                    "approval_id": approval.challenge_id,
                    "approval_state": approval_state,
                },
            )
            return result

        external_call_policy = self.external_call_policy.evaluate(action_id=decision.action, external_call=decision.external_call)
        if not external_call_policy.allowed:
            result = RouteResult(
                ok=False,
                status="offline_blocked",
                decision=decision,
                reason=external_call_policy.reason,
                plan=plan,
            )
            self._record(
                "manager_agent.offline_blocked",
                message,
                ctx,
                result,
                extra={
                    "external_policy_decision": external_call_policy.reason,
                    "external_action_allowlisted": external_call_policy.action_allowlisted,
                },
            )
            return result

        if decision.action == "safe_follow_up":
            result = RouteResult(ok=False, status="needs_clarification", decision=decision, reason="unknown_intent", plan=plan)
            extra = {"suggestions": list(self.router.SAFE_SUGGESTIONS)}
            warnings = list(ctx.get("guard_warnings") or [])
            if pre_exec_guard.decision == GuardDecision.ALLOW_WITH_WARNING:
                warnings.extend(pre_exec_guard.reasons)
            if warnings:
                extra["guard_decision"] = GuardDecision.ALLOW_WITH_WARNING.value
                extra["guard_warnings"] = sorted(set(warnings))
            self._record("manager_agent.needs_clarification", message, ctx, result, extra=extra)
            return result

        extra: dict[str, Any] = {}
        warnings = list(ctx.get("guard_warnings") or [])
        if pre_exec_guard.decision == GuardDecision.ALLOW_WITH_WARNING:
            warnings.extend(pre_exec_guard.reasons)
        if warnings:
            extra["guard_decision"] = GuardDecision.ALLOW_WITH_WARNING.value
            extra["guard_warnings"] = sorted(set(warnings))
        if approval and approval.allowed:
            extra["approval_state"] = "approved"
            extra["approval_id"] = approval.challenge_id
        if decision.external_call:
            extra["external_policy_decision"] = external_call_policy.reason
            extra["external_action_allowlisted"] = external_call_policy.action_allowlisted

        result = RouteResult(ok=True, status="routed", decision=decision, plan=plan)
        self._record("manager_agent.routed", message, ctx, result, extra=extra or None)
        return result

    def _record(
        self,
        event_type: str,
        message: str,
        context: Mapping[str, Any],
        result: RouteResult,
        *,
        extra: Mapping[str, Any] | None = None,
    ) -> None:
        payload = {
            "message": str(message or "")[:500],
            "tenant": str(context.get("tenant") or "default"),
            "user": str(context.get("user") or "system"),
            "tool": result.decision.tool,
            "action": result.decision.action,
            "intent": result.decision.intent,
            "execution_mode": result.decision.execution_mode,
            "status": result.status,
            "ok": result.ok,
            "reason": result.reason,
            "confirm_required": result.confirm_required,
            "risk_assessment": result.plan.risk_assessment if result.plan else "unknown",
        }
        if extra:
            payload.update(dict(extra))
        payload["audit_states"] = self._derive_audit_states(result=result, payload=payload)
        self.event_bus.emit(event_type, payload)
        result.audit_event = payload
        if callable(self.audit_logger):
            self.audit_logger(payload)

    def _approval_scope(self, decision: RouteDecision) -> str:
        if decision.external_call:
            return "external"
        return "write"

    def _record_approval_event(self, payload: dict[str, Any]) -> None:
        self.event_bus.emit(payload.get("event", "approval.unknown"), payload)
        if callable(self.audit_logger):
            self.audit_logger(payload)

    @staticmethod
    def _approval_state_from_reason(reason: str) -> str:
        reason_map = {
            "approval_required": "confirm_required",
            "approval_pending": "pending",
            "approval_denied": "denied",
            "approval_expired": "expired",
        }
        return reason_map.get(str(reason), "denied")

    @staticmethod
    def _derive_audit_states(*, result: RouteResult, payload: Mapping[str, Any]) -> list[str]:
        states: list[str] = []

        if result.status == "confirm_required":
            states.append("confirm_required")
        if payload.get("approval_state") == "denied":
            states.append("denied")
        if payload.get("approval_state") == "expired":
            states.append("expired")
        if payload.get("approval_state") == "pending":
            states.append("pending")
        if payload.get("approval_state") == "approved":
            states.append("approved")
        if result.status in {"blocked", "offline_blocked", "needs_review"}:
            states.append("blocked")
        if result.ok and result.status == "routed":
            states.append("routed")
        if result.status in {"needs_clarification", "failed"}:
            states.append("failed")
        if not result.ok and not states:
            states.append("failed")

        deduplicated: list[str] = []
        for state in states:
            if state not in deduplicated:
                deduplicated.append(state)
        return deduplicated
