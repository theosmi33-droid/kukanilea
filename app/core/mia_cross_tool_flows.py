from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable
import uuid

ActionHandler = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class RegisteredAction:
    name: str
    kind: str  # read | write
    offline_safe: bool


@dataclass(frozen=True)
class FlowDefinition:
    flow_id: str
    trigger: str
    title: str
    value: str


DEFAULT_ACTIONS: dict[str, RegisteredAction] = {
    "create_task": RegisteredAction("create_task", kind="write", offline_safe=True),
    "create_calendar_event": RegisteredAction("create_calendar_event", kind="write", offline_safe=True),
    "create_followup_task": RegisteredAction("create_followup_task", kind="write", offline_safe=True),
    "propose_project_task": RegisteredAction("propose_project_task", kind="read", offline_safe=True),
    "search_documents": RegisteredAction("search_documents", kind="read", offline_safe=True),
    "summarize_document": RegisteredAction("summarize_document", kind="read", offline_safe=True),
    "suggest_meeting_slots": RegisteredAction("suggest_meeting_slots", kind="read", offline_safe=True),
    "queue_local_review": RegisteredAction("queue_local_review", kind="write", offline_safe=True),
}


FLOW_CATALOG: tuple[FlowDefinition, ...] = (
    FlowDefinition(
        flow_id="email_to_task",
        trigger="email.received",
        title="E-Mail -> Aufgabe",
        value="Schnelle Erfassung von To-dos aus eingehenden Mails.",
    ),
    FlowDefinition(
        flow_id="email_to_meeting_proposal",
        trigger="email.received",
        title="E-Mail -> Termin-Vorschlag",
        value="Terminwünsche werden mit Vorschlag + Confirm-Gate vorbereitet.",
    ),
    FlowDefinition(
        flow_id="messenger_to_followup_task",
        trigger="messenger.received",
        title="Messenger -> Follow-up-Aufgabe",
        value="Offene Chat-Zusagen werden als Follow-up-Task vorgeschlagen.",
    ),
    FlowDefinition(
        flow_id="document_to_deadline_task",
        trigger="document.processed",
        title="Dokument -> Frist/Aufgabe",
        value="Erkannte Fristen werden in umsetzbare Aufgaben überführt.",
    ),
    FlowDefinition(
        flow_id="invoice_receipt_triage",
        trigger="document.processed",
        title="Rechnung/Beleg -> Suche/Zusammenfassung/Folgeaktion",
        value="Belege werden lokal auffindbar und in Folgeaktionen überführt.",
    ),
)


class MiaFlowEngine:
    """Small, testable flow planner for cross-tool MIA ROI flows."""

    def __init__(
        self,
        *,
        handlers: dict[str, ActionHandler] | None = None,
        registered_actions: dict[str, RegisteredAction] | None = None,
    ) -> None:
        self.registered_actions = dict(registered_actions or DEFAULT_ACTIONS)
        self.handlers = handlers or {}
        self._proposals: dict[str, dict[str, Any]] = {}
        self.audit_log: list[dict[str, Any]] = []

    def list_flows(self) -> list[dict[str, str]]:
        return [
            {
                "flow_id": item.flow_id,
                "trigger": item.trigger,
                "title": item.title,
                "value": item.value,
            }
            for item in FLOW_CATALOG
        ]

    def plan(self, trigger: str, payload: dict[str, Any]) -> dict[str, Any]:
        trigger_n = str(trigger or "").strip().lower()
        flow_plan = self._build_flow_plan(trigger_n, payload)
        if not flow_plan:
            return {"status": "ignored", "reason": "no_matching_flow", "trigger": trigger_n}

        proposal_id = f"mia-{uuid.uuid4().hex[:10]}"
        now = datetime.now(UTC).isoformat(timespec="seconds")

        confirm_points = [step["action"] for step in flow_plan["steps"] if step["confirm_required"]]
        audit_points = [
            "mia.proposal.created",
            "mia.confirm.requested" if confirm_points else "mia.execution.started",
            "mia.execution.finished",
        ]
        proposal = {
            "proposal_id": proposal_id,
            "status": "proposal_required" if confirm_points else "ready",
            "created_at": now,
            "flow_id": flow_plan["flow_id"],
            "flow_title": flow_plan["flow_title"],
            "trigger": trigger_n,
            "steps": flow_plan["steps"],
            "confirm_points": confirm_points,
            "audit_points": audit_points,
            "degradation": flow_plan["degradation"],
        }
        self._proposals[proposal_id] = proposal
        self._audit("mia.proposal.created", proposal_id, {"flow_id": flow_plan["flow_id"]})
        if confirm_points:
            self._audit("mia.confirm.requested", proposal_id, {"confirm_points": confirm_points})
        return proposal

    def execute(self, proposal_id: str, *, confirmed: bool) -> dict[str, Any]:
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            return {"status": "not_found", "proposal_id": proposal_id}

        if proposal.get("confirm_points") and not confirmed:
            self._audit("mia.confirm.denied", proposal_id, {"reason": "explicit_confirm_required"})
            return {"status": "confirmation_required", "proposal_id": proposal_id}

        self._audit("mia.execution.started", proposal_id, {"flow_id": proposal.get("flow_id")})
        results: list[dict[str, Any]] = []
        for step in proposal.get("steps", []):
            action = str(step.get("action") or "")
            payload = dict(step.get("payload") or {})
            if action not in self.registered_actions:
                results.append({"action": action, "status": "blocked", "reason": "action_not_registered"})
                continue
            if step.get("mode") == "propose":
                results.append({"action": action, "status": "proposed_only", "reason": step.get("reason", "missing_context")})
                continue
            handler = self.handlers.get(action)
            if handler is None:
                results.append({"action": action, "status": "simulated", "payload": payload})
                continue
            results.append({"action": action, "status": "executed", "result": handler(payload)})

        self._audit("mia.execution.finished", proposal_id, {"results": len(results)})
        return {"status": "executed", "proposal_id": proposal_id, "results": results}

    def _audit(self, event_type: str, proposal_id: str, payload: dict[str, Any]) -> None:
        self.audit_log.append(
            {
                "timestamp": datetime.now(UTC).isoformat(timespec="seconds"),
                "event_type": event_type,
                "proposal_id": proposal_id,
                "payload": payload,
            }
        )

    def _build_flow_plan(self, trigger: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        subject = str(payload.get("subject") or "").lower()
        text = " ".join(
            str(payload.get(key) or "") for key in ("subject", "body", "message", "ocr_text", "filename")
        ).lower()

        if trigger == "email.received" and (subject.startswith("todo:") or "aufgabe" in text):
            title = str(payload.get("subject") or "TODO aus E-Mail").split(":", 1)[-1].strip() or "TODO aus E-Mail"
            return {
                "flow_id": "email_to_task",
                "flow_title": "E-Mail -> Aufgabe",
                "degradation": "offline_local_task_store",
                "steps": [
                    {
                        "action": "create_task",
                        "confirm_required": True,
                        "mode": "confirm",
                        "payload": {
                            "tenant": str(payload.get("tenant") or "KUKANILEA"),
                            "title": title,
                            "details": str(payload.get("body") or ""),
                            "source_ref": str(payload.get("email_id") or payload.get("id") or ""),
                        },
                    }
                ],
            }

        if trigger == "email.received" and any(word in text for word in ("termin", "meeting", "kalender")):
            start_at = str(payload.get("suggested_start") or "").strip()
            mode = "confirm" if start_at else "propose"
            reason = "missing_suggested_start" if not start_at else ""
            return {
                "flow_id": "email_to_meeting_proposal",
                "flow_title": "E-Mail -> Termin-Vorschlag",
                "degradation": "local_timeslot_suggestion_only",
                "steps": [
                    {
                        "action": "suggest_meeting_slots",
                        "confirm_required": False,
                        "mode": "execute",
                        "payload": {"text": text, "tenant": str(payload.get("tenant") or "KUKANILEA")},
                    },
                    {
                        "action": "create_calendar_event",
                        "confirm_required": True,
                        "mode": mode,
                        "reason": reason,
                        "payload": {
                            "tenant": str(payload.get("tenant") or "KUKANILEA"),
                            "title": str(payload.get("subject") or "Termin aus E-Mail"),
                            "starts_at": start_at,
                        },
                    },
                ],
            }

        if trigger == "messenger.received" and any(word in text for word in ("follow", "nachfassen", "bitte", "erinner")):
            thread_id = str(payload.get("thread_id") or "").strip()
            return {
                "flow_id": "messenger_to_followup_task",
                "flow_title": "Messenger -> Follow-up-Aufgabe",
                "degradation": "local_followup_queue",
                "steps": [
                    {
                        "action": "create_followup_task",
                        "confirm_required": True,
                        "mode": "confirm" if thread_id else "propose",
                        "reason": "missing_thread_id" if not thread_id else "",
                        "payload": {
                            "tenant": str(payload.get("tenant") or "KUKANILEA"),
                            "thread_id": thread_id,
                            "title": str(payload.get("title") or "Messenger Follow-up"),
                        },
                    }
                ],
            }

        if trigger == "document.processed" and any(word in text for word in ("frist", "deadline", "fällig", "faellig")):
            deadline = str(payload.get("detected_deadline") or "").strip()
            return {
                "flow_id": "document_to_deadline_task",
                "flow_title": "Dokument -> Frist/Aufgabe",
                "degradation": "proposal_only_without_deadline",
                "steps": [
                    {
                        "action": "create_task",
                        "confirm_required": True,
                        "mode": "confirm" if deadline else "propose",
                        "reason": "missing_deadline" if not deadline else "",
                        "payload": {
                            "tenant": str(payload.get("tenant") or "KUKANILEA"),
                            "title": f"Frist prüfen: {str(payload.get('filename') or 'Dokument')}",
                            "details": str(payload.get("ocr_text") or ""),
                            "due_date": deadline,
                        },
                    }
                ],
            }

        if trigger == "document.processed" and any(word in text for word in ("rechnung", "invoice", "beleg", "receipt")):
            index_available = bool(payload.get("search_index_available", True))
            followup_mode = "confirm" if str(payload.get("amount_due") or "").strip() else "propose"
            return {
                "flow_id": "invoice_receipt_triage",
                "flow_title": "Rechnung/Beleg -> Suche/Zusammenfassung/Folgeaktion",
                "degradation": "queue_local_review" if not index_available else "none",
                "steps": [
                    {
                        "action": "search_documents" if index_available else "queue_local_review",
                        "confirm_required": not index_available,
                        "mode": "confirm" if not index_available else "execute",
                        "payload": {
                            "tenant": str(payload.get("tenant") or "KUKANILEA"),
                            "query": str(payload.get("filename") or "beleg"),
                        },
                    },
                    {
                        "action": "summarize_document",
                        "confirm_required": False,
                        "mode": "execute",
                        "payload": {
                            "tenant": str(payload.get("tenant") or "KUKANILEA"),
                            "text": str(payload.get("ocr_text") or ""),
                        },
                    },
                    {
                        "action": "create_followup_task",
                        "confirm_required": True,
                        "mode": followup_mode,
                        "reason": "missing_amount_due" if followup_mode == "propose" else "",
                        "payload": {
                            "tenant": str(payload.get("tenant") or "KUKANILEA"),
                            "title": "Rechnung nachfassen",
                            "details": f"Dokument: {str(payload.get('filename') or '')}",
                        },
                    },
                ],
            }

        return None
