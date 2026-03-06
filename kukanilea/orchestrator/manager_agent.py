from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Callable, Mapping

from .approval_runtime import ApprovalRuntime

INJECTION_PATTERNS = (
    re.compile(r"\bignore\s+previous\s+instructions\b", re.IGNORECASE),
    re.compile(r"\bignore\s+all\s+instructions\b", re.IGNORECASE),
    re.compile(r"\bsystem\s+prompt\b", re.IGNORECASE),
    re.compile(r"\bdeveloper\s+message\b", re.IGNORECASE),
    re.compile(r"\bbypass\s+(policy|safety|confirm)\b", re.IGNORECASE),
)


@dataclass(frozen=True)
class ActionSpec:
    action: str
    tool: str
    parameter_schema: dict[str, str]
    confirm_required: bool = False
    external_call: bool = False


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

    ACTION_REGISTRY: dict[str, ActionSpec] = {
        "dashboard_summary": ActionSpec("dashboard_summary", "dashboard", {"tenant": "str"}),
        "customer_lookup": ActionSpec("customer_lookup", "crm", {"customer_id": "str"}),
        "task_create": ActionSpec("task_create", "tasks", {"title": "str", "description": "str"}, confirm_required=True),
        "appointment_create": ActionSpec(
            "appointment_create",
            "calendar",
            {"summary": "str", "date": "str"},
            confirm_required=True,
        ),
        "invoice_search": ActionSpec("invoice_search", "dms", {"query": "str"}),
        "material_status": ActionSpec("material_status", "warehouse", {"query": "str"}),
        "messenger_reply": ActionSpec(
            "messenger_reply",
            "messenger",
            {"channel": "str", "message": "str"},
            confirm_required=True,
            external_call=True,
        ),
    }

    INTENT_LIBRARY: tuple[IntentSpec, ...] = (
        IntentSpec(
            name="dashboard_status",
            patterns=(
                re.compile(r"\b(dashboard|status|health|übersicht)\b", re.IGNORECASE),
            ),
            candidate_actions=("dashboard_summary",),
        ),
        IntentSpec(
            name="customer_lookup",
            patterns=(
                re.compile(r"\b(kunde|kundennummer|kdnr|wer\s+ist)\b", re.IGNORECASE),
            ),
            candidate_actions=("customer_lookup",),
            required_entities=("customer_id",),
        ),
        IntentSpec(
            name="task_management",
            patterns=(
                re.compile(r"\b(aufgabe|task|todo|einsatz)\b", re.IGNORECASE),
            ),
            candidate_actions=("task_create",),
            required_entities=("title",),
        ),
        IntentSpec(
            name="appointment_planning",
            patterns=(
                re.compile(r"\b(termin|kalender|baustelle\s+einplanen)\b", re.IGNORECASE),
            ),
            candidate_actions=("appointment_create",),
            required_entities=("date", "summary"),
        ),
        IntentSpec(
            name="invoice_search",
            patterns=(
                re.compile(r"\b(rechnung|angebot|lieferschein|beleg)\b", re.IGNORECASE),
            ),
            candidate_actions=("invoice_search",),
        ),
        IntentSpec(
            name="material_check",
            patterns=(
                re.compile(r"\b(material|lager|bestand)\b", re.IGNORECASE),
            ),
            candidate_actions=("material_status",),
        ),
        IntentSpec(
            name="messenger_response",
            patterns=(
                re.compile(r"\b(nachricht|messenger|antworten|whatsapp|telegram)\b", re.IGNORECASE),
            ),
            candidate_actions=("messenger_reply",),
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
                action_specs = [self.ACTION_REGISTRY[name] for name in spec.candidate_actions if name in self.ACTION_REGISTRY]
                highest_risk = "low"
                if any(action.external_call for action in action_specs):
                    highest_risk = "high"
                elif any(action.confirm_required for action in action_specs):
                    highest_risk = "medium"

                if missing:
                    mode = "propose"
                elif any(action.confirm_required for action in action_specs):
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
        action_name = next((action for action in plan.candidate_actions if action in self.ACTION_REGISTRY), "")
        if not action_name:
            return RouteDecision(
                intent=plan.intent_name,
                tool="chatbot",
                action="safe_follow_up",
                execution_mode="propose",
            )

        spec = self.ACTION_REGISTRY[action_name]
        mode = plan.execution_mode
        if plan.missing_context:
            mode = "propose"
        return RouteDecision(
            intent=plan.intent_name,
            tool=spec.tool,
            action=spec.action,
            requires_confirm=spec.confirm_required,
            external_call=spec.external_call,
            execution_mode=mode,
        )

    def validate_parameters(self, action: str, params: Mapping[str, Any] | None) -> bool:
        spec = self.ACTION_REGISTRY.get(action)
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
        approval_runtime: ApprovalRuntime | None = None,
    ) -> None:
        self.router = DeterministicToolRouter()
        self.event_bus = event_bus or EventBus()
        self.audit_logger = audit_logger
        self.external_calls_enabled = bool(external_calls_enabled)
        self.approvals = approval_runtime or ApprovalRuntime(audit_logger=self._record_approval_event)

    def route(self, message: str, context: Mapping[str, Any] | None = None) -> RouteResult:
        ctx = dict(context or {})

        injection, patterns = self.router.contains_injection(message)
        if injection:
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
            self._record("manager_agent.blocked", message, ctx, result, extra={"patterns": patterns, "suggestions": list(self.router.SAFE_SUGGESTIONS)})
            return result

        plan = self.router.build_plan(message)
        decision = self.router.select(plan)

        if decision.action not in self.router.ACTION_REGISTRY and decision.action not in {"safe_follow_up", "safe_fallback"}:
            result = RouteResult(ok=False, status="blocked", decision=decision, reason="action_not_registered", plan=plan)
            self._record("manager_agent.blocked", message, ctx, result)
            return result

        if plan.candidate_actions and not self.router.validate_parameters(decision.action, ctx.get("params")):
            result = RouteResult(ok=False, status="blocked", decision=decision, reason="schema_validation_failed", plan=plan)
            self._record("manager_agent.blocked", message, ctx, result)
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
            result = RouteResult(
                ok=False,
                status="confirm_required",
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
                extra={"approval_id": approval.challenge_id},
            )
            return result

        if decision.external_call and not self.external_calls_enabled:
            result = RouteResult(
                ok=False,
                status="offline_blocked",
                decision=decision,
                reason="external_calls_disabled",
                plan=plan,
            )
            self._record("manager_agent.offline_blocked", message, ctx, result)
            return result

        if decision.action == "safe_follow_up":
            result = RouteResult(ok=False, status="needs_clarification", decision=decision, reason="unknown_intent", plan=plan)
            self._record("manager_agent.needs_clarification", message, ctx, result, extra={"suggestions": list(self.router.SAFE_SUGGESTIONS)})
            return result

        result = RouteResult(ok=True, status="routed", decision=decision, plan=plan)
        self._record("manager_agent.routed", message, ctx, result)
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
