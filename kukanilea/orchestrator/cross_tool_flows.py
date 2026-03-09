from __future__ import annotations

import traceback
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from kukanilea.guards import detect_prompt_injection, neutralize_untrusted_text
from kukanilea.idempotency import GLOBAL_IDEMPOTENCY_STORE, canonical_hash

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

    def is_registered(self, action_id: str) -> bool:
        return action_id in self._handlers

    def execute(self, action_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        handler = self._handlers.get(action_id)
        if handler is None:
            raise KeyError(f"action_not_registered:{action_id}")
        return handler(payload)

    def action_ids(self) -> set[str]:
        return set(self._handlers)


class CrossToolFlowEngine:
    def __init__(
        self,
        *,
        action_registry: AtomicActionRegistry,
        flows: Mapping[str, FlowDefinition],
    ) -> None:
        self.action_registry = action_registry
        self.flows = dict(flows)
        self.idempotency_store = GLOBAL_IDEMPOTENCY_STORE
        self._validate_flow_definitions()

    def _validate_flow_definitions(self) -> None:
        for flow in self.flows.values():
            step_ids = {step.step_id for step in flow.steps}
            write_steps = {step.step_id for step in flow.steps if step.writes_state}
            confirmation_points = set(flow.confirmation_points)

            unknown_confirmation_points = confirmation_points - step_ids
            if unknown_confirmation_points:
                unknown = ", ".join(sorted(unknown_confirmation_points))
                raise ValueError(f"flow:{flow.flow_id}:unknown_confirmation_points:{unknown}")

            unguarded_write_steps = write_steps - confirmation_points
            if unguarded_write_steps:
                missing = ", ".join(sorted(unguarded_write_steps))
                raise ValueError(f"flow:{flow.flow_id}:write_steps_require_confirmation:{missing}")

            for step in flow.steps:
                if not self.action_registry.is_registered(step.action_id):
                    raise ValueError(
                        f"flow:{flow.flow_id}:step:{step.step_id}:action_not_registered:{step.action_id}"
                    )

    def run(
        self,
        *,
        flow_id: str,
        context: Mapping[str, Any],
        confirmations: Mapping[str, bool] | None = None,
        tool_health: Mapping[str, bool] | None = None,
    ) -> FlowExecutionResult:
        flow = self.flows.get(flow_id)
        if flow is None:
            return FlowExecutionResult(
                ok=False,
                status="failed",
                flow_id=flow_id,
                failures=[{"code": "flow_not_found", "flow_id": flow_id}],
                audit_evidence=[{"event": "flow.failed", "reason": "flow_not_found", "flow_id": flow_id}],
            )

        confirmations = confirmations or {}
        health = tool_health or {}
        result = FlowExecutionResult(ok=True, status="completed", flow_id=flow.flow_id)
        idem_scope = f"flow:{flow.flow_id}:{str(context.get('tenant_id') or 'default')}"
        idem_key = str(context.get("idempotency_key") or "").strip()
        idem_token = ""

        if idem_key and any(step.writes_state for step in flow.steps):
            req_hash = canonical_hash(
                {
                    "context": {k: context[k] for k in sorted(context) if k != "idempotency_key"},
                    "confirmations": dict(confirmations),
                }
            )
            decision = self.idempotency_store.begin(
                scope=idem_scope,
                key=idem_key,
                request_hash=req_hash,
                ttl_seconds=24 * 60 * 60,
            )
            if decision.status == "replay":
                replay = dict(decision.response or {})
                replay_result = FlowExecutionResult(
                    ok=bool(replay.get("ok", True)),
                    status=str(replay.get("status") or "completed"),
                    flow_id=str(replay.get("flow_id") or flow.flow_id),
                    executed_steps=list(replay.get("executed_steps") or []),
                    proposals=list(replay.get("proposals") or []),
                    failures=list(replay.get("failures") or []),
                    audit_evidence=list(replay.get("audit_evidence") or []),
                    outputs=dict(replay.get("outputs") or {}),
                )
                replay_result.audit_evidence.append(
                    {"event": "flow.idempotent_replay", "flow_id": flow.flow_id, "idempotency_key": idem_key}
                )
                return replay_result
            if decision.status == "conflict":
                result.ok = False
                result.status = "failed"
                result.failures.append({"code": "idempotency_conflict", "flow_id": flow.flow_id})
                return result
            if decision.status == "in_flight":
                result.ok = False
                result.status = "failed"
                result.failures.append({"code": "idempotency_in_flight", "flow_id": flow.flow_id})
                return result
            idem_token = str(decision.token or "")

        missing = [k for k in flow.required_context if k not in context]
        if missing:
            result.ok = False
            result.status = "propose_and_ask_confirmation"
            result.proposals.append({"type": "missing_context", "required": missing})
            result.audit_evidence.append(
                {"event": "flow.context_missing", "flow_id": flow.flow_id, "missing": missing}
            )
            return result

        run_context: dict[str, Any] = dict(context)
        for step in flow.steps:
            if step.required_tool and health.get(step.required_tool) is False:
                result.status = "degraded"
                result.proposals.append(
                    {
                        "type": "fallback",
                        "step_id": step.step_id,
                        "reason": "tool_unhealthy",
                        "policy": flow.fallback_policy,
                    }
                )
                result.audit_evidence.append(
                    {
                        "event": "flow.fallback_applied",
                        "flow_id": flow.flow_id,
                        "step_id": step.step_id,
                        "reason": "tool_unhealthy",
                    }
                )
                continue

            requires_approval = step.step_id in flow.confirmation_points
            if requires_approval and not confirmations.get(step.step_id, False):
                result.status = "propose_and_ask_confirmation"
                result.ok = False
                result.proposals.append(
                    {
                        "type": "confirm_required",
                        "step_id": step.step_id,
                        "action_id": step.action_id,
                    }
                )
                result.audit_evidence.append(
                    {
                        "event": "flow.confirm_required",
                        "flow_id": flow.flow_id,
                        "step_id": step.step_id,
                    }
                )
                continue

            try:
                output = self.action_registry.execute(step.action_id, run_context)
            except Exception as exc:  # deterministic failure reporting
                trace = traceback.format_exc()
                result.ok = False
                result.status = "failed"
                result.failures.append(
                    {
                        "code": "action_failed",
                        "step_id": step.step_id,
                        "action_id": step.action_id,
                        "error": str(exc),
                        "traceback": trace,
                    }
                )
                result.audit_evidence.append(
                    {
                        "event": "flow.step_failed",
                        "flow_id": flow.flow_id,
                        "step_id": step.step_id,
                        "action_id": step.action_id,
                        "error": str(exc),
                        "traceback": trace,
                    }
                )
                break

            run_context.update(output)
            result.outputs.update(output)
            result.executed_steps.append(step.step_id)
            result.audit_evidence.append(
                {
                    "event": "flow.step_executed",
                    "flow_id": flow.flow_id,
                    "step_id": step.step_id,
                    "action_id": step.action_id,
                }
            )

        if idem_token:
            if result.ok and result.status in {"completed", "degraded"} and result.executed_steps:
                self.idempotency_store.complete_success(
                    scope=idem_scope,
                    key=idem_key,
                    token=idem_token,
                    response={
                        "ok": result.ok,
                        "status": result.status,
                        "flow_id": result.flow_id,
                        "executed_steps": result.executed_steps,
                        "proposals": result.proposals,
                        "failures": result.failures,
                        "audit_evidence": result.audit_evidence,
                        "outputs": result.outputs,
                    },
                    status_code=200,
                    ttl_seconds=24 * 60 * 60,
                )
            else:
                self.idempotency_store.complete_failure(scope=idem_scope, key=idem_key, token=idem_token)

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
        lambda p: {
            "document_text": _extract_untrusted_text(p, "document_text"),
            "document_has_due_hint": any(
                marker in _extract_untrusted_text(p, "document_text").lower()
                for marker in ("frist", "fällig", "due", "deadline")
            ),
        },
    )
    registry.register(
        "document_classify_deadline_task",
        lambda p: {
            "classification_label": (
                "deadline_candidate" if p.get("document_has_due_hint") else "general_document"
            ),
            "task_title": (
                "Frist aus Dokument prüfen"
                if p.get("document_has_due_hint")
                else str(p.get("task_title") or "Dokument prüfen")[:120]
            ),
            "default_deadline": (
                str(p.get("default_deadline") or "")
                or ("asap" if p.get("document_has_due_hint") else "")
            ),
        },
    )
    registry.register(
        "document_suggest_deadline_task",
        lambda p: {
            "suggested_deadline": str(p.get("default_deadline") or ""),
            "task_title": str(p.get("task_title") or "Dokument prüfen")[:120],
            "task_proposal_state": "ready_for_confirm",
        },
    )
    registry.register(
        "messenger_extract_followup",
        lambda p: {"followup_summary": _extract_untrusted_text(p, "message_text")[:200]},
    )
    registry.register(
        "task_prepare_calendar_entry",
        lambda p: {
            "calendar_title": (_extract_untrusted_text(p, "task_title") or "Aufgabe")[:120],
            "calendar_start": str(p.get("task_due_at") or p.get("suggested_start") or ""),
        },
    )
    registry.register(
        "calendar_create_event",
        lambda p: {
            "calendar_event_ref": f"evt:{str(p.get('task_id') or p.get('task_title') or 'task')[:40]}"
        },
    )
    registry.register(
        "upload_extract_project_hint",
        lambda p: {
            "project_hint": (_extract_untrusted_text(p, "upload_project_hint") or _extract_untrusted_text(p, "filename")).strip(),
            "upload_title": (_extract_untrusted_text(p, "filename") or "Datei")[:120],
        },
    )
    registry.register(
        "project_link_upload",
        lambda p: {
            "project_upload_ref": (
                f"project:{str(p.get('project_id') or p.get('project_hint') or 'unknown')[:40]}"
                f"/file:{str(p.get('upload_id') or p.get('upload_title') or 'upload')[:40]}"
            )
        },
    )
    registry.register(
        "messenger_extract_task",
        lambda p: {
            "task_title": (_extract_untrusted_text(p, "message_text") or "Follow-up")[:120],
            "task_notes": _extract_untrusted_text(p, "message_text"),
        },
    )
    registry.register(
        "invoice_extract_due",
        lambda p: {
            "invoice_id": (
                _extract_untrusted_text(p, "invoice_id")
                or _extract_untrusted_text(p, "document_id")
                or "unbekannt"
            )[:50],
            "invoice_due_date": (
                _extract_untrusted_text(p, "invoice_due_date")
                or _extract_untrusted_text(p, "default_due_date")
            ),
        },
    )
    registry.register(
        "invoice_propose_reminder",
        lambda p: {
            "reminder_proposal": (
                f"Zahlungserinnerung für Rechnung {(_extract_untrusted_text(p, 'invoice_id') or 'unbekannt')[:50]} "
                f"zum Termin {(_extract_untrusted_text(p, 'invoice_due_date') or 'offen')} erstellen"
            )
        },
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
            audit_events=("flow.step_executed", "flow.confirm_required", "flow.step_failed"),
            fallback_policy="propose_then_manual_queue",
        ),
        "flow_task_to_calendar": FlowDefinition(
            flow_id="flow_task_to_calendar",
            title="Aufgabe -> Kalender",
            trigger="task_due_scheduled",
            steps=(
                FlowStep("prepare_calendar_entry", "task_prepare_calendar_entry"),
                FlowStep("create_calendar_event", "calendar_create_event", writes_state=True, required_tool="calendar"),
            ),
            required_context=("task_id", "task_title"),
            confirmation_points=("create_calendar_event",),
            audit_events=("flow.step_executed", "flow.confirm_required", "flow.fallback_applied"),
            fallback_policy="propose_calendar_event_without_sync",
        ),
        "flow_upload_to_project": FlowDefinition(
            flow_id="flow_upload_to_project",
            title="Upload -> Projekt",
            trigger="file_uploaded",
            steps=(
                FlowStep("extract_project_hint", "upload_extract_project_hint"),
                FlowStep("link_upload", "project_link_upload", writes_state=True, required_tool="projects"),
            ),
            required_context=("upload_id", "filename"),
            confirmation_points=("link_upload",),
            audit_events=("flow.step_executed", "flow.confirm_required", "flow.fallback_applied"),
            fallback_policy="queue_upload_for_manual_project_mapping",
        ),
        "flow_messenger_to_task": FlowDefinition(
            flow_id="flow_messenger_to_task",
            title="Messenger -> Aufgabe",
            trigger="message_received",
            steps=(
                FlowStep("extract_task", "messenger_extract_task"),
                FlowStep("create_task", "document_suggest_deadline_task", writes_state=True, required_tool="tasks"),
            ),
            required_context=("message_text",),
            confirmation_points=("create_task",),
            audit_events=("flow.step_executed", "flow.confirm_required", "flow.step_failed"),
            fallback_policy="propose_then_manual_queue",
        ),
        "flow_invoice_reminder_proposal": FlowDefinition(
            flow_id="flow_invoice_reminder_proposal",
            title="Rechnung -> Zahlungserinnerungs-Vorschlag",
            trigger="invoice_received",
            steps=(
                FlowStep("extract_invoice_due", "invoice_extract_due"),
                FlowStep("propose_reminder", "invoice_propose_reminder"),
            ),
            required_context=("invoice_id",),
            confirmation_points=(),
            audit_events=("flow.step_executed", "flow.fallback_applied"),
            fallback_policy="propose_with_missing_finance_context",
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
            audit_events=("flow.step_executed", "flow.confirm_required", "flow.fallback_applied"),
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
            audit_events=("flow.step_executed", "flow.fallback_applied"),
            fallback_policy="propose_alternative_slot",
        ),
        "flow_document_extract_deadline_task": FlowDefinition(
            flow_id="flow_document_extract_deadline_task",
            title="Dokument/Upload -> OCR/Extraktion -> Frist/Aufgabe vorschlagen",
            trigger="document_uploaded",
            steps=(
                FlowStep("extract_document", "document_extract", required_tool="ocr"),
                FlowStep("classify_document", "document_classify_deadline_task"),
                FlowStep("propose_deadline_task", "document_suggest_deadline_task", writes_state=True, required_tool="tasks"),
            ),
            required_context=("document_text",),
            confirmation_points=("propose_deadline_task",),
            audit_events=("flow.step_executed", "flow.confirm_required", "flow.fallback_applied"),
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
            audit_events=("flow.step_executed", "flow.confirm_required"),
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
            audit_events=("flow.step_executed", "flow.confirm_required", "flow.step_failed"),
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
            audit_events=("flow.step_executed", "flow.confirm_required"),
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
            audit_events=("flow.step_executed", "flow.confirm_required", "flow.fallback_applied"),
            fallback_policy="propose_then_request_missing_context",
        ),
    }
