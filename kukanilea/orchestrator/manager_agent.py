from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Callable, Mapping

from .action_catalog import create_action_registry
from .action_registry import ActionRegistry

CONFIRM_TOKENS = {"1", "true", "yes", "confirm", "ja"}
INJECTION_PATTERNS = (
    re.compile(r"\bignore\s+previous\s+instructions\b", re.IGNORECASE),
    re.compile(r"\bignore\s+all\s+instructions\b", re.IGNORECASE),
    re.compile(r"\bsystem\s+prompt\b", re.IGNORECASE),
    re.compile(r"\bdeveloper\s+message\b", re.IGNORECASE),
    re.compile(r"\bbypass\s+(policy|safety|confirm)\b", re.IGNORECASE),
)

HIGH_RISK_RUNTIME_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("destructive_request", re.compile(r"\b(delete|wipe|drop|destroy|purge)\b.{0,40}\b(files?|backups?|database|all)\b", re.IGNORECASE)),
    ("exfiltration", re.compile(r"\b(exfiltrat\w*|send|upload|post)\b.{0,40}\b(https?|webhook|extern|remote|ftp)\b", re.IGNORECASE)),
)

MEDIUM_RISK_RUNTIME_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("policy_override", re.compile(r"\bbypass\s+(policy|safety|confirm)\b", re.IGNORECASE)),
    ("prompt_leak", re.compile(r"\b(reveal|show|dump|print)\b.{0,40}\b(system\s+prompt|developer\s+message)\b", re.IGNORECASE)),
)

LOW_RISK_WARN_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("quoted_attack_example", re.compile(r"\bexample\b.*\b(ignore|bypass)\b", re.IGNORECASE)),
    ("quoted_attack_example", re.compile(r"\bprompt\s*injection\b", re.IGNORECASE)),
)


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
class GuardrailEvaluation:
    decision: str
    reasons: tuple[str, ...]
    matched_signals: tuple[str, ...]
    normalized_message: str


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
            name="material_check",
            patterns=(
                re.compile(r"\b(material|lager|bestand)\b", re.IGNORECASE),
            ),
            candidate_actions=("warehouse.material.status",),
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
    ) -> None:
        self.router = DeterministicToolRouter()
        self.event_bus = event_bus or EventBus()
        self.audit_logger = audit_logger
        self.external_calls_enabled = bool(external_calls_enabled)

    def _normalize_untrusted(self, message: str) -> str:
        compact = re.sub(r"\s+", " ", str(message or "")).strip()
        return compact[:4000]

    def _evaluate_untrusted(self, message: str, *, stage: str, action: str | None = None) -> GuardrailEvaluation:
        normalized = self._normalize_untrusted(message)
        matched: set[str] = set()
        reasons: list[str] = []

        for signal, pattern in HIGH_RISK_RUNTIME_PATTERNS:
            if pattern.search(normalized):
                matched.add(signal)

        for signal, pattern in MEDIUM_RISK_RUNTIME_PATTERNS:
            if pattern.search(normalized):
                matched.add(signal)

        for signal, pattern in LOW_RISK_WARN_PATTERNS:
            if pattern.search(normalized):
                matched.add(signal)

        if any(s in matched for s in {"destructive_request", "exfiltration"}):
            return GuardrailEvaluation(
                decision="block",
                reasons=(f"{stage}_high_risk_signal",),
                matched_signals=tuple(sorted(matched)),
                normalized_message=normalized,
            )

        if any(s in matched for s in {"policy_override", "prompt_leak"}):
            return GuardrailEvaluation(
                decision="route_to_review",
                reasons=(f"{stage}_possible_policy_manipulation",),
                matched_signals=tuple(sorted(matched)),
                normalized_message=normalized,
            )

        if "quoted_attack_example" in matched:
            return GuardrailEvaluation(
                decision="allow_with_warning",
                reasons=(f"{stage}_suspicious_but_contextual",),
                matched_signals=tuple(sorted(matched)),
                normalized_message=normalized,
            )

        if stage == "pre_execution" and action and action not in self.router.action_registry.actions and action not in {"safe_follow_up", "safe_fallback"}:
            return GuardrailEvaluation(
                decision="block",
                reasons=("pre_execution_action_not_registered",),
                matched_signals=("action_hallucination",),
                normalized_message=normalized,
            )

        return GuardrailEvaluation(
            decision="allow",
            reasons=(f"{stage}_no_risk_signal",),
            matched_signals=(),
            normalized_message=normalized,
        )

    def route(self, message: str, context: Mapping[str, Any] | None = None) -> RouteResult:
        ctx = dict(context or {})

        pre_intent = self._evaluate_untrusted(message, stage="pre_intent")
        if pre_intent.decision in {"block", "route_to_review"}:
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
                status="blocked" if pre_intent.decision == "block" else "route_to_review",
                decision=decision,
                reason="runtime_guardrail_pre_intent",
                plan=blocked_plan,
            )
            self._record(
                "manager_agent.security_block",
                message,
                ctx,
                result,
                extra={
                    "guardrail_decision": pre_intent.decision,
                    "guardrail_reasons": list(pre_intent.reasons),
                    "guardrail_signals": list(pre_intent.matched_signals),
                },
            )
            return result

        if pre_intent.decision == "allow_with_warning":
            self.event_bus.emit(
                "manager_agent.guardrail_warning",
                {
                    "decision": pre_intent.decision,
                    "reasons": list(pre_intent.reasons),
                    "signals": list(pre_intent.matched_signals),
                    "message": pre_intent.normalized_message,
                },
            )

        injection, patterns = self.router.contains_injection(message)
        if injection and pre_intent.decision != "allow_with_warning":
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

        pre_execution = self._evaluate_untrusted(message, stage="pre_execution", action=decision.action)
        if pre_execution.decision in {"block", "route_to_review"}:
            blocked = RouteResult(
                ok=False,
                status="blocked" if pre_execution.decision == "block" else "route_to_review",
                decision=RouteDecision(intent="security_blocked", tool="chatbot", action="safe_fallback", execution_mode="propose"),
                reason="runtime_guardrail_pre_execution",
                plan=plan,
            )
            self._record(
                "manager_agent.security_block",
                message,
                ctx,
                blocked,
                extra={
                    "guardrail_decision": pre_execution.decision,
                    "guardrail_reasons": list(pre_execution.reasons),
                    "guardrail_signals": list(pre_execution.matched_signals),
                },
            )
            return blocked

        if decision.action not in self.router.action_registry.actions and decision.action not in {"safe_follow_up", "safe_fallback"}:
            result = RouteResult(ok=False, status="blocked", decision=decision, reason="action_not_registered", plan=plan)
            self._record("manager_agent.blocked", message, ctx, result)
            return result

        if plan.candidate_actions and not self.router.validate_parameters(decision.action, ctx.get("params")):
            result = RouteResult(ok=False, status="blocked", decision=decision, reason="schema_validation_failed", plan=plan)
            self._record("manager_agent.blocked", message, ctx, result)
            return result

        confirm = _confirm_token(ctx.get("confirm"))
        if (decision.requires_confirm or plan.execution_mode == "confirm") and not confirm:
            result = RouteResult(
                ok=False,
                status="confirm_required",
                decision=decision,
                reason="confirm_gate",
                confirm_required=True,
                plan=plan,
            )
            self._record("manager_agent.confirm_blocked", message, ctx, result)
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


def _confirm_token(value: Any) -> bool:
    token = str(value or "").strip().lower()
    return token in CONFIRM_TOKENS
