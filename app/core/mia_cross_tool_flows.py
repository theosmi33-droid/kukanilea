from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable

from app.mia_audit import (
    MIA_EVENT_CONFIRM_DENIED,
    MIA_EVENT_CONFIRM_GRANTED,
    MIA_EVENT_CONFIRM_REQUESTED,
    MIA_EVENT_EXECUTION_FINISHED,
    MIA_EVENT_EXECUTION_STARTED,
    MIA_EVENT_PROPOSAL_CREATED,
    emit_mia_event_safe,
)

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
    "create_project_proposal": RegisteredAction("create_project_proposal", kind="write", offline_safe=True),
    "search_documents": RegisteredAction("search_documents", kind="read", offline_safe=True),
    "summarize_document": RegisteredAction("summarize_document", kind="read", offline_safe=True),
    "suggest_meeting_slots": RegisteredAction("suggest_meeting_slots", kind="read", offline_safe=True),
    "queue_local_review": RegisteredAction("queue_local_review", kind="write", offline_safe=True),
}


FLOW_CATALOG: tuple[FlowDefinition, ...] = (
    FlowDefinition(
        flow_id="inquiry_to_task_project_calendar_proposal",
        trigger="inquiry.received",
        title="Anfrage -> Task/Projekt -> Termin",
        value="Produktiv-kritischer Kernflow: Anfrage wird als Task/Projekt plus Termin-Vorschlag vorbereitet.",
    ),
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
        flow_id="messenger_to_task",
        trigger="messenger.received",
        title="Messenger -> Aufgabe",
        value="Zusagen oder Follow-ups aus dem Chat direkt als Aufgabe erfassen.",
    ),
    FlowDefinition(
        flow_id="document_to_deadline_task",
        trigger="document.processed",
        title="Dokument -> Frist/Aufgabe",
        value="Erkannte Fristen werden in umsetzbare Aufgaben überführt.",
    ),
    FlowDefinition(
        flow_id="upload_to_project_proposal",
        trigger="document.processed",
        title="Upload -> Projekt-Vorschlag",
        value="Eingehende Dokumente (Entwürfe/Angebote) werden als Projekt-Vorschlag aufbereitet.",
    ),
    FlowDefinition(
        flow_id="invoice_receipt_triage",
        trigger="document.processed",
        title="Rechnung/Beleg -> Suche/Zusammenfassung/Folgeaktion",
        value="Belege werden lokal auffindbar und in Folgeaktionen überführt.",
    ),
    FlowDefinition(
        flow_id="task_to_calendar_proposal",
        trigger="task.created",
        title="Aufgabe -> Kalender-Vorschlag",
        value="Aufgaben mit Zeitbezug werden direkt als Kalender-Vorschlag vorbereitet.",
    ),
)


MIA_FLOW_AUDIT_EVENT_MATRIX: dict[str, dict[str, tuple[str, ...]]] = {
    "email_to_task": {
        "plan": (MIA_EVENT_PROPOSAL_CREATED, MIA_EVENT_CONFIRM_REQUESTED),
        "execute_confirmed": (
            MIA_EVENT_CONFIRM_GRANTED,
            MIA_EVENT_EXECUTION_STARTED,
            "mia.step.started",
            "mia.step.simulated",
            MIA_EVENT_EXECUTION_FINISHED,
        ),
        "execute_unconfirmed": (MIA_EVENT_CONFIRM_DENIED,),
    }
}


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
            "clarifications": flow_plan.get("clarifications", []),
        }
        self._proposals[proposal_id] = proposal
        self._audit(
            MIA_EVENT_PROPOSAL_CREATED,
            proposal_id,
            {"flow_id": flow_plan["flow_id"], "tenant_id": str(payload.get("tenant") or "KUKANILEA")},
        )
        if confirm_points:
            self._audit(
                MIA_EVENT_CONFIRM_REQUESTED,
                proposal_id,
                {"confirm_points": confirm_points, "tenant_id": str(payload.get("tenant") or "KUKANILEA")},
            )
        return proposal

    def execute(self, proposal_id: str, *, confirmed: bool) -> dict[str, Any]:
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            return {"status": "not_found", "proposal_id": proposal_id}

        tenant_id = str(proposal.get("steps", [{}])[0].get("payload", {}).get("tenant") or "KUKANILEA")
        if proposal.get("confirm_points") and not confirmed:
            self._audit(MIA_EVENT_CONFIRM_DENIED, proposal_id, {"reason": "explicit_confirm_required", "tenant_id": tenant_id})
            return {"status": "confirmation_required", "proposal_id": proposal_id}
        if proposal.get("confirm_points") and confirmed:
            self._audit(MIA_EVENT_CONFIRM_GRANTED, proposal_id, {"tenant_id": tenant_id})

        self._audit(MIA_EVENT_EXECUTION_STARTED, proposal_id, {"flow_id": proposal.get("flow_id"), "tenant_id": tenant_id})
        results: list[dict[str, Any]] = []
        for index, step in enumerate(proposal.get("steps", []), start=1):
            action = str(step.get("action") or "")
            payload = dict(step.get("payload") or {})
            self._audit("mia.step.started", proposal_id, {"step_index": index, "action": action, "tenant_id": tenant_id})
            if action not in self.registered_actions:
                results.append({"action": action, "status": "blocked", "reason": "action_not_registered"})
                self._audit(
                    "mia.step.blocked",
                    proposal_id,
                    {"step_index": index, "action": action, "reason": "action_not_registered", "tenant_id": tenant_id},
                )
                continue
            action_def = self.registered_actions[action]
            if action_def.kind == "write" and not step.get("confirm_required", False):
                results.append({"action": action, "status": "blocked", "reason": "write_requires_confirm"})
                self._audit(
                    "mia.step.blocked",
                    proposal_id,
                    {
                        "step_index": index,
                        "action": action,
                        "reason": "write_requires_confirm",
                        "tenant_id": tenant_id,
                    },
                )
                continue
            if action_def.kind == "write" and not confirmed:
                results.append({"action": action, "status": "blocked", "reason": "confirmation_required"})
                self._audit(
                    "mia.step.blocked",
                    proposal_id,
                    {
                        "step_index": index,
                        "action": action,
                        "reason": "confirmation_required",
                        "tenant_id": tenant_id,
                    },
                )
                continue
            if step.get("mode") == "propose":
                results.append({"action": action, "status": "proposed_only", "reason": step.get("reason", "missing_context")})
                self._audit(
                    "mia.step.proposed",
                    proposal_id,
                    {
                        "step_index": index,
                        "action": action,
                        "reason": step.get("reason", "missing_context"),
                        "tenant_id": tenant_id,
                    },
                )
                continue
            handler = self.handlers.get(action)
            if handler is None:
                results.append({"action": action, "status": "simulated", "payload": payload})
                self._audit("mia.step.simulated", proposal_id, {"step_index": index, "action": action, "tenant_id": tenant_id})
                continue
            results.append({"action": action, "status": "executed", "result": handler(payload)})
            self._audit("mia.step.executed", proposal_id, {"step_index": index, "action": action, "tenant_id": tenant_id})

        self._audit(MIA_EVENT_EXECUTION_FINISHED, proposal_id, {"results": len(results), "tenant_id": tenant_id})
        return {"status": "executed", "proposal_id": proposal_id, "results": results}

    def _audit(self, event_type: str, proposal_id: str, payload: dict[str, Any]) -> None:
        tenant_id = str(payload.get("tenant_id") or "KUKANILEA")
        self.audit_log.append(
            {
                "timestamp": datetime.now(UTC).isoformat(timespec="seconds"),
                "event_type": event_type,
                "proposal_id": proposal_id,
                "payload": payload,
            }
        )
        emit_mia_event_safe(
            event_type=event_type,
            entity_type="mia_flow_proposal",
            entity_ref=proposal_id,
            tenant_id=tenant_id,
            payload=payload,
        )

    def _build_flow_plan(self, trigger: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        subject = str(payload.get("subject") or "").lower()
        subject_raw = str(payload.get("subject") or "")
        text = " ".join(
            str(payload.get(key) or "")
            for key in ("subject", "body", "message", "ocr_text", "filename", "title", "description")
        ).lower()

        # 0. Anfrage -> Task/Projekt -> Termin-Vorschlag (Kernflow)
        if trigger == "inquiry.received" and any(word in text for word in ("anfrage", "inquiry", "angebot", "projekt", "termin")):
            task_title = str(payload.get("task_title") or payload.get("subject") or "").strip()
            project_name = str(payload.get("project_name") or "").strip()
            starts_at = str(payload.get("suggested_start") or payload.get("due_at") or "").strip()
            clarifications: list[str] = []
            if not task_title:
                clarifications.append("Welche konkrete Aufgabe soll aus der Anfrage entstehen?")
            if not project_name:
                clarifications.append("Wie soll das Projekt heißen?")
            if not starts_at:
                clarifications.append("Wann soll der Termin stattfinden?")
            return {
                "flow_id": "inquiry_to_task_project_calendar_proposal",
                "flow_title": "Anfrage -> Task/Projekt -> Termin",
                "degradation": "proposal_chain_for_missing_context" if clarifications else "offline_local_delivery_chain",
                "clarifications": clarifications,
                "steps": [
                    {
                        "action": "create_task",
                        "confirm_required": True,
                        "mode": "confirm" if task_title else "propose",
                        "reason": "missing_task_title" if not task_title else "",
                        "payload": {
                            "tenant": str(payload.get("tenant") or "KUKANILEA"),
                            "title": task_title or "Aufgabe aus Anfrage",
                            "details": str(payload.get("body") or payload.get("description") or ""),
                            "source_ref": str(payload.get("inquiry_id") or payload.get("id") or ""),
                        },
                    },
                    {
                        "action": "create_project_proposal",
                        "confirm_required": True,
                        "mode": "confirm" if project_name else "propose",
                        "reason": "missing_project_name" if not project_name else "",
                        "payload": {
                            "tenant": str(payload.get("tenant") or "KUKANILEA"),
                            "name": project_name or "Projekt aus Anfrage",
                            "description": str(payload.get("body") or "Projektvorschlag aus Anfrage"),
                        },
                    },
                    {
                        "action": "suggest_meeting_slots",
                        "confirm_required": False,
                        "mode": "execute",
                        "payload": {"text": text, "tenant": str(payload.get("tenant") or "KUKANILEA")},
                    },
                    {
                        "action": "create_calendar_event",
                        "confirm_required": True,
                        "mode": "confirm" if starts_at else "propose",
                        "reason": "missing_start_time" if not starts_at else "",
                        "payload": {
                            "tenant": str(payload.get("tenant") or "KUKANILEA"),
                            "title": str(payload.get("meeting_title") or "Termin aus Anfrage"),
                            "start_at": starts_at,
                            "description": str(payload.get("body") or ""),
                        },
                    },
                ],
            }

        # 1. E-Mail -> Aufgabe
        if trigger == "email.received" and any(word in text for word in ("todo", "aufgabe", "task")):
            title = subject_raw.split(":", 1)[-1].strip() if subject.startswith("todo:") else subject_raw.strip()
            if not title:
                title = str(payload.get("task_title") or "").strip()
            has_title = bool(title)
            return {
                "flow_id": "email_to_task",
                "flow_title": "E-Mail -> Aufgabe",
                "degradation": "proposal_only_without_task_title" if not has_title else "offline_local_task_store",
                "clarifications": ["Welchen konkreten Titel soll die Aufgabe haben?"] if not has_title else [],
                "steps": [
                    {
                        "action": "create_task",
                        "confirm_required": True,
                        "mode": "confirm" if has_title else "propose",
                        "reason": "missing_task_title" if not has_title else "",
                        "payload": {
                            "tenant": str(payload.get("tenant") or "KUKANILEA"),
                            "title": title or "TODO aus E-Mail",
                            "details": str(payload.get("body") or ""),
                            "source_ref": str(payload.get("email_id") or payload.get("id") or ""),
                        },
                    }
                ],
            }

        # 2. E-Mail -> Termin-Vorschlag
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

        # 3. Messenger -> Follow-up-Aufgabe
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

        # 4. Messenger -> Aufgabe (Alias / Requested Name)
        if trigger == "messenger.received" and any(
            word in text for word in ("follow", "nachfassen", "bitte", "erinner", "task", "aufgabe")
        ):
            thread_id = str(payload.get("thread_id") or "").strip()
            return {
                "flow_id": "messenger_to_task",
                "flow_title": "Messenger -> Aufgabe",
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
                            "description": str(payload.get("message") or ""),
                        },
                    }
                ],
            }

        # 5. Dokument -> Frist/Aufgabe
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

        # 6. Upload -> Projekt-Vorschlag
        if (trigger == "document.processed" or trigger == "upload.finished") and any(
            word in text for word in ("projekt", "entwurf", "angebot", "proposal")
        ):
            project_name = str(payload.get("project_name") or "").strip()
            if not project_name and "projekt:" in text:
                try:
                    project_name = text.split("projekt:")[1].split(".")[0].split("\n")[0].strip().title()
                except Exception:
                    project_name = ""

            has_project_name = bool(project_name)
            return {
                "flow_id": "upload_to_project_proposal",
                "flow_title": "Upload -> Projekt-Vorschlag",
                "degradation": "summarize_only_without_name",
                "clarifications": ["Wie soll das neue Projekt heißen?"] if not has_project_name else [],
                "steps": [
                    {
                        "action": "summarize_document",
                        "confirm_required": False,
                        "mode": "execute",
                        "payload": {
                            "tenant": str(payload.get("tenant") or "KUKANILEA"),
                            "text": str(payload.get("ocr_text") or ""),
                            "filename": str(payload.get("filename") or "Dokument"),
                        },
                    },
                    {
                        "action": "create_project_proposal",
                        "confirm_required": True,
                        "mode": "confirm" if has_project_name else "propose",
                        "reason": "missing_project_name" if not has_project_name else "",
                        "payload": {
                            "tenant": str(payload.get("tenant") or "KUKANILEA"),
                            "name": project_name or "Neues Projekt",
                            "description": f"Projektvorschlag aus Dokument {str(payload.get('filename') or '')}",
                        },
                    },
                ],
            }

        # 7. Rechnung/Beleg -> Suche/Zusammenfassung/Folgeaktion
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

        # 8. Aufgabe -> Kalender-Vorschlag
        if (trigger == "task.created" or trigger == "task.updated") and any(
            word in text for word in ("termin", "meeting", "besprechung", "kalender", "appointment")
        ):
            start_at = str(payload.get("due_at") or payload.get("suggested_start") or "").strip()
            mode = "confirm" if start_at else "propose"
            reason = "missing_start_time" if not start_at else ""
            return {
                "flow_id": "task_to_calendar_proposal",
                "flow_title": "Aufgabe -> Kalender-Vorschlag",
                "degradation": "manual_calendar_entry",
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
                            "title": str(payload.get("title") or "Termin aus Aufgabe"),
                            "start_at": start_at,
                            "description": str(payload.get("description") or ""),
                        },
                    },
                ],
            }

        return None
