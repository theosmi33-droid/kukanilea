from __future__ import annotations

from copy import deepcopy
from typing import Any

WORKFLOW_TEMPLATE_MARKER_PREFIX = "workflow_template:"

_WORKFLOW_TEMPLATES: dict[str, dict[str, Any]] = {
    "mail_followup_task": {
        "key": "mail_followup_task",
        "name": "Mail -> Follow-up + Task",
        "description": (
            "Reagiert auf Postfach-Eingang und erstellt eine Follow-up-Aufgabe "
            "sowie einen allgemeinen Review-Task."
        ),
        "rule_payload": {
            "name": "Workflow: Mail -> Follow-up + Task",
            "description": (
                "Template fuer Postfach-Eingang: erstellt Follow-up und Review-Task."
            ),
            "max_executions_per_minute": 20,
            "triggers": [
                {
                    "trigger_type": "eventlog",
                    "config": {
                        "allowed_event_types": [
                            "mailbox_message_received",
                            "mailbox_thread_intake_extracted",
                        ]
                    },
                }
            ],
            "conditions": [],
            "actions": [
                {
                    "action_type": "create_followup",
                    "config": {
                        "title": "Postfach Follow-up pruefen",
                        "owner": "unassigned",
                        "requires_confirm": False,
                    },
                },
                {
                    "action_type": "create_task",
                    "config": {
                        "title": "CRM/Lead aus Postfach pruefen",
                        "details": "Automatisch erzeugt aus Mail-Workflow",
                        "requires_confirm": False,
                    },
                },
            ],
        },
    },
    "invoice_document_review": {
        "key": "invoice_document_review",
        "name": "Dokument/OCR -> Review Task",
        "description": (
            "Reagiert auf Dokument- und OCR-Events und erstellt einen "
            "Rechnungs-/Dokumenten-Review-Task."
        ),
        "rule_payload": {
            "name": "Workflow: Dokument/OCR -> Review Task",
            "description": (
                "Template fuer Dokumenteingang und OCR-Abschluss mit Review-Task."
            ),
            "max_executions_per_minute": 20,
            "triggers": [
                {
                    "trigger_type": "eventlog",
                    "config": {
                        "allowed_event_types": [
                            "source_file_ingested",
                            "knowledge_document_ingested",
                            "knowledge_ocr_ingested",
                            "autonomy_ocr_done",
                        ]
                    },
                }
            ],
            "conditions": [],
            "actions": [
                {
                    "action_type": "create_task",
                    "config": {
                        "title": "Rechnung/Dokument pruefen",
                        "details": "Automatisch erzeugt aus Dokument/OCR-Workflow",
                        "requires_confirm": False,
                    },
                }
            ],
        },
    },
    "task_done_email": {
        "key": "task_done_email",
        "name": "Task Done -> E-Mail",
        "description": (
            "Reagiert auf Task-Bewegungen in Done/Resolved und erstellt einen "
            "E-Mail-Sendevorgang (mit bestaetigter Pending-Action)."
        ),
        "rule_payload": {
            "name": "Workflow: Task Done -> E-Mail",
            "description": "Template fuer erledigte Tasks mit E-Mail-Benachrichtigung.",
            "max_executions_per_minute": 20,
            "triggers": [
                {
                    "trigger_type": "eventlog",
                    "config": {"allowed_event_types": ["task_moved"]},
                }
            ],
            "conditions": [
                {
                    "condition_type": "context_match",
                    "config": {"field": "task_status", "equals": "RESOLVED"},
                }
            ],
            "actions": [
                {
                    "action_type": "email_send",
                    "config": {
                        "to": ["max@demo.invalid"],
                        "subject": "Task abgeschlossen ({entity_id})",
                        "body_template": (
                            "Automatisches Update aus {event_type} fuer Task {entity_id}."
                        ),
                        "requires_confirm": True,
                    },
                }
            ],
        },
    },
}


def workflow_template_marker(template_key: str) -> str:
    key = str(template_key or "").strip()
    return f"[{WORKFLOW_TEMPLATE_MARKER_PREFIX}{key}]"


def list_workflow_templates() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for key in sorted(_WORKFLOW_TEMPLATES.keys()):
        row = _WORKFLOW_TEMPLATES[key]
        payload = dict(row.get("rule_payload") or {})
        trigger_types = [
            str(item.get("trigger_type") or "").strip()
            for item in (payload.get("triggers") or [])
            if isinstance(item, dict)
        ]
        action_types = [
            str(item.get("action_type") or "").strip()
            for item in (payload.get("actions") or [])
            if isinstance(item, dict)
        ]
        items.append(
            {
                "key": key,
                "name": str(row.get("name") or key),
                "description": str(row.get("description") or ""),
                "trigger_types": [v for v in trigger_types if v],
                "action_types": [v for v in action_types if v],
            }
        )
    return items


def get_workflow_template(template_key: str) -> dict[str, Any] | None:
    key = str(template_key or "").strip()
    if not key:
        return None
    row = _WORKFLOW_TEMPLATES.get(key)
    if row is None:
        return None
    return deepcopy(row)
