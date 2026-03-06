from __future__ import annotations

import traceback
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from kukanilea.guards import detect_prompt_injection, neutralize_untrusted_text

from .audit_schema import build_audit_event

ActionHandler = Callable[[Mapping[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class FlowStep:
    step_id: str
    action_id: str
    writes_state: bool = False
    required_tool: str | None = None


@dataclass(frozen=True)
class FlowDefinition:
    flow_id: str
    title: str
    trigger: str
    steps: tuple[FlowStep, ...]
    required_context: tuple[str, ...]
    confirmation_points: tuple[str, ...]
    audit_events: tuple[str, ...]
    fallback_policy: str


@dataclass
class FlowExecutionResult:
    ok: bool
    status: str
    flow_id: str
    executed_steps: list[str] = field(default_factory=list)
    proposals: list[dict[str, Any]] = field(default_factory=list)
    failures: list[dict[str, Any]] = field(default_factory=list)
    audit_evidence: list[dict[str, Any]] = field(default_factory=list)
    outputs: dict[str, Any] = field(default_factory=dict)


class AtomicActionRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, ActionHandler] = {}

    def register(self, action_id: str, handler: ActionHandler) -> None:
        self._handlers[action_id] = handler

    def execute(self, action_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        handler = self._handlers.get(action_id)
        if handler is None:
            raise KeyError(f"action_not_registered:{action_id}")
        return handler(payload)


class CrossToolFlowEngine:
    def __init__(
        self,
        *,
        action_registry: AtomicActionRegistry,
        flows: Mapping[str, FlowDefinition],
    ) -> None:
        self.action_registry = action_registry
        self.flows = dict(flows)

    def run(
        self,
        *,
        flow_id: str,
        context: Mapping[str, Any],
        confirmations: Mapping[str, bool] | None = None,
        tool_health: Mapping[str, bool] | None = None,
    ) -> FlowExecutionResult:
        flow = self.flows.get(flow_id)
        tenant = str(context.get("tenant") or "default")
        user = str(context.get("user") or "system")
        if flow is None:
            return FlowExecutionResult(
                ok=False,
                status="failed",
                flow_id=flow_id,
                failures=[{"code": "flow_not_found", "flow_id": flow_id}],
                audit_evidence=[
                    build_audit_event(
                        "execution_failed",
                        tenant=tenant,
                        user=user,
                        action=flow_id,
                        tool="flow_engine",
                        intent="flow_execution",
                        risk="medium",
                        execution_mode="execute",
                        status="failed",
                        reason="flow_not_found",
                        meta={"flow_id": flow_id},
                    )
                ],
            )

        confirmations = confirmations or {}
        health = tool_health or {}
        result = FlowExecutionResult(ok=True, status="completed", flow_id=flow.flow_id)
        result.audit_evidence.append(build_audit_event("intent_detected", tenant=tenant, user=user, action=flow.flow_id, tool="flow_engine", intent=flow.trigger, risk="low", execution_mode="propose", status="detected", reason="trigger_received"))
        result.audit_evidence.append(build_audit_event("action_selected", tenant=tenant, user=user, action=flow.flow_id, tool="flow_engine", intent=flow.trigger, risk="low", execution_mode="execute", status="selected", reason="flow_loaded"))
        result.audit_evidence.append(build_audit_event("execution_started", tenant=tenant, user=user, action=flow.flow_id, tool="flow_engine", intent=flow.trigger, risk="medium", execution_mode="execute", status="started", reason="flow_execution_started"))

        missing = [k for k in flow.required_context if k not in context]
        if missing:
            result.ok = False
            result.status = "propose_and_ask_confirmation"
            result.proposals.append({"type": "missing_context", "required": missing})
            result.audit_evidence.append(build_audit_event("route_blocked", tenant=tenant, user=user, action=flow.flow_id, tool="flow_engine", intent=flow.trigger, risk="low", execution_mode="propose", status="propose_and_ask_confirmation", reason="context_missing", meta={"flow_id": flow.flow_id, "missing": missing}))
            return result

        run_context: dict[str, Any] = dict(context)
        for step in flow.steps:
            if step.required_tool and health.get(step.required_tool) is False:
                result.status = "degraded"
                result.proposals.append({"type": "fallback", "step_id": step.step_id, "reason": "tool_unhealthy", "policy": flow.fallback_policy})
                result.audit_evidence.append(build_audit_event("route_blocked", tenant=tenant, user=user, action=step.action_id, tool=str(step.required_tool or "flow_engine"), intent=flow.trigger, risk="medium", execution_mode="propose", status="degraded", reason="tool_unhealthy", meta={"flow_id": flow.flow_id, "step_id": step.step_id}))
                continue

            if step.writes_state and not confirmations.get(step.step_id, False):
                result.status = "propose_and_ask_confirmation"
                result.ok = False
                result.proposals.append({"type": "confirm_required", "step_id": step.step_id, "action_id": step.action_id})
                result.audit_evidence.append(build_audit_event("confirm_requested", tenant=tenant, user=user, action=step.action_id, tool=str(step.required_tool or "flow_engine"), intent=flow.trigger, risk="medium", execution_mode="confirm", status="confirm_required", reason="write_requires_confirm", meta={"flow_id": flow.flow_id, "step_id": step.step_id}))
                continue

            try:
                output = self.action_registry.execute(step.action_id, run_context)
            except Exception as exc:  # deterministic failure reporting
                trace = traceback.format_exc()
                result.ok = False
                result.status = "failed"
                result.failures.append({"code": "action_failed", "step_id": step.step_id, "action_id": step.action_id, "error": str(exc), "traceback": trace})
                result.audit_evidence.append(build_audit_event("execution_failed", tenant=tenant, user=user, action=step.action_id, tool=str(step.required_tool or "flow_engine"), intent=flow.trigger, risk="high", execution_mode="execute", status="failed", reason="action_failed", meta={"flow_id": flow.flow_id, "step_id": step.step_id, "error": str(exc), "traceback": trace}))
                break

            run_context.update(output)
            result.outputs.update(output)
            result.executed_steps.append(step.step_id)
            result.audit_evidence.append(build_audit_event("execution_succeeded", tenant=tenant, user=user, action=step.action_id, tool=str(step.required_tool or "flow_engine"), intent=flow.trigger, risk="low", execution_mode="execute", status="completed", reason="step_executed", meta={"flow_id": flow.flow_id, "step_id": step.step_id}))

        if result.ok and result.status in {"completed", "degraded"}:
            result.audit_evidence.append(build_audit_event("execution_succeeded", tenant=tenant, user=user, action=flow.flow_id, tool="flow_engine", intent=flow.trigger, risk="low", execution_mode="execute", status=result.status, reason="flow_completed", meta={"executed_steps": list(result.executed_steps)}))

        return result


def _extract_untrusted_text(payload: Mapping[str, Any], key: str) -> str:
    raw = str(payload.get(key) or "")
    blocked, _ = detect_prompt_injection(raw)
    safe = neutralize_untrusted_text(raw)
    if blocked:
        return ""
    return safe


def create_default_registry() -> AtomicActionRegistry:
    registry = AtomicActionRegistry()

    registry.register(
        "email_extract_task",
        lambda p: {
            "task_title": (_extract_untrusted_text(p, "email_subject") or "Neue Anfrage").strip()[:120],
            "task_notes": _extract_untrusted_text(p, "email_body"),
        },
    )
    registry.register(
        "email_match_project",
        lambda p: {
            "project_id": next(
                (
                    str(project["id"])
                    for project in (p.get("projects") or [])
                    if str(project.get("keyword") or "").lower()
                    in str(p.get("email_subject") or "").lower()
                ),
                "",
            )
        },
    )
    registry.register(
        "calendar_check_conflict",
        lambda p: {
            "calendar_conflict": any(
                slot.get("start") == p.get("requested_start")
                for slot in (p.get("calendar_entries") or [])
            )
        },
    )
    registry.register(
        "calendar_propose_slot",
        lambda p: {
            "proposed_start": str(p.get("fallback_start") or p.get("requested_start") or ""),
            "proposal_reason": "conflict" if p.get("calendar_conflict") else "no_conflict",
        },
    )
    registry.register(
        "document_extract",
        lambda p: {"document_text": _extract_untrusted_text(p, "document_text")},
    )
    registry.register(
        "document_suggest_deadline_task",
        lambda p: {
            "suggested_deadline": str(p.get("default_deadline") or ""),
            "task_title": str(p.get("task_title") or "Dokument prüfen"),
        },
    )
    registry.register(
        "messenger_extract_followup",
        lambda p: {"followup_summary": _extract_untrusted_text(p, "message_text")[:200]},
    )
    registry.register(
        "system_create_audit_entry",
        lambda p: {
            "audit_entry": {
                "event": str(p.get("event_type") or "unknown_event")[:50],
                "severity": str(p.get("severity") or "INFO")[:10],
            }
        },
    )
    registry.register(
        "system_notify_admin",
        lambda p: {
            "admin_hint": f"Admin-Hinweis: {str(p.get('event_type') or 'unknown_event')[:50]}"
        },
    )
    registry.register(
        "deadline_sync_calendar_task",
        lambda p: {"sync_ref": f"sync:{p.get('deadline_id', 'n/a')}"},
    )
    registry.register(
        "document_detect_customer_project",
        lambda p: {
            "detected_customer": str(p.get("customer_hint") or ""),
            "project_id": str(p.get("project_hint") or p.get("project_id") or ""),
        },
    )
    registry.register(
        "document_propose_action",
        lambda p: {"suggested_action": str(p.get("suggested_action") or "Aufgabe anlegen")},
    )
    return registry


def build_core_flows() -> dict[str, FlowDefinition]:
    return {
        "flow_email_to_task": FlowDefinition(
            flow_id="flow_email_to_task",
            title="E-Mail -> Aufgabe",
            trigger="email_received",
            steps=(
                FlowStep("extract_email", "email_extract_task"),
                FlowStep("create_task", "document_suggest_deadline_task", writes_state=True, required_tool="tasks"),
            ),
            required_context=("email_subject", "email_body"),
            confirmation_points=("create_task",),
            audit_events=("execution_succeeded", "confirm_requested", "execution_failed"),
            fallback_policy="propose_then_manual_queue",
        ),
        "flow_email_project_task": FlowDefinition(
            flow_id="flow_email_project_task",
            title="E-Mail -> Projektzuordnung -> Aufgabe",
            trigger="email_received",
            steps=(
                FlowStep("extract_email", "email_extract_task"),
                FlowStep("match_project", "email_match_project", required_tool="projects"),
                FlowStep("create_task", "document_suggest_deadline_task", writes_state=True, required_tool="tasks"),
            ),
            required_context=("email_subject", "email_body", "projects"),
            confirmation_points=("create_task",),
            audit_events=("execution_succeeded", "confirm_requested", "route_blocked"),
            fallback_policy="propose_then_manual_assignment",
        ),
        "flow_calendar_conflict_suggest": FlowDefinition(
            flow_id="flow_calendar_conflict_suggest",
            title="Kalenderkonflikt prüfen -> Termin vorschlagen",
            trigger="appointment_requested",
            steps=(
                FlowStep("check_conflict", "calendar_check_conflict", required_tool="calendar"),
                FlowStep("propose_slot", "calendar_propose_slot"),
            ),
            required_context=("requested_start", "calendar_entries"),
            confirmation_points=(),
            audit_events=("execution_succeeded", "route_blocked"),
            fallback_policy="propose_alternative_slot",
        ),
        "flow_document_extract_deadline_task": FlowDefinition(
            flow_id="flow_document_extract_deadline_task",
            title="Dokument/Upload -> OCR/Extraktion -> Frist/Aufgabe vorschlagen",
            trigger="document_uploaded",
            steps=(
                FlowStep("extract_document", "document_extract", required_tool="ocr"),
                FlowStep("propose_deadline_task", "document_suggest_deadline_task", writes_state=True, required_tool="tasks"),
            ),
            required_context=("document_text",),
            confirmation_points=("propose_deadline_task",),
            audit_events=("execution_succeeded", "confirm_requested", "route_blocked"),
            fallback_policy="degrade_to_manual_review",
        ),
        "flow_messenger_followup_task": FlowDefinition(
            flow_id="flow_messenger_followup_task",
            title="Messenger-Nachricht -> Follow-up-Aufgabe",
            trigger="message_received",
            steps=(
                FlowStep("extract_followup", "messenger_extract_followup"),
                FlowStep("create_followup_task", "document_suggest_deadline_task", writes_state=True, required_tool="tasks"),
            ),
            required_context=("message_text",),
            confirmation_points=("create_followup_task",),
            audit_events=("execution_succeeded", "confirm_requested"),
            fallback_policy="propose_then_manual_queue",
        ),
        "flow_license_event_audit_admin": FlowDefinition(
            flow_id="flow_license_event_audit_admin",
            title="Lizenz-/Systemereignis -> Audit-Eintrag -> Admin-Hinweis",
            trigger="system_event",
            steps=(
                FlowStep("create_audit", "system_create_audit_entry", writes_state=True, required_tool="audit"),
                FlowStep("notify_admin", "system_notify_admin", writes_state=True, required_tool="settings"),
            ),
            required_context=("event_type",),
            confirmation_points=("create_audit", "notify_admin"),
            audit_events=("execution_succeeded", "confirm_requested", "execution_failed"),
            fallback_policy="queue_for_admin_review",
        ),
        "flow_deadline_sync": FlowDefinition(
            flow_id="flow_deadline_sync",
            title="Erinnerung/Deadline -> Kalender + Aufgabe synchronisieren",
            trigger="deadline_due",
            steps=(
                FlowStep("sync_deadline", "deadline_sync_calendar_task", writes_state=True, required_tool="calendar"),
            ),
            required_context=("deadline_id",),
            confirmation_points=("sync_deadline",),
            audit_events=("execution_succeeded", "confirm_requested"),
            fallback_policy="propose_without_sync",
        ),
        "flow_document_intake_classify_action": FlowDefinition(
            flow_id="flow_document_intake_classify_action",
            title="Dokumenteingang -> Kunde/Projekt erkennen -> vorgeschlagene Aktion",
            trigger="document_received",
            steps=(
                FlowStep("detect_entities", "document_detect_customer_project"),
                FlowStep("propose_action", "document_propose_action", writes_state=True, required_tool="tasks"),
            ),
            required_context=("customer_hint",),
            confirmation_points=("propose_action",),
            audit_events=("execution_succeeded", "confirm_requested", "route_blocked"),
            fallback_policy="propose_then_request_missing_context",
        ),
    }
