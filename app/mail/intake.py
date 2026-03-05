from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.modules.kalender.contracts import build_appointment_proposal


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(slots=True)
class IntakeEnvelope:
    source: str
    thread_id: str
    sender: str
    subject: str
    snippets: list[str] = field(default_factory=list)
    attachments: list[dict[str, Any]] = field(default_factory=list)
    suggested_actions: list[dict[str, Any]] = field(default_factory=list)
    requires_confirm: bool = True
    created_at: str = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_intake_payload(payload: dict[str, Any]) -> IntakeEnvelope:
    source = str(payload.get("source") or "mail").strip().lower() or "mail"
    sender = str(payload.get("sender") or payload.get("from") or "").strip()
    subject = str(payload.get("subject") or "").strip()
    thread_id = str(payload.get("thread_id") or payload.get("conversation_id") or "").strip()

    snippets_raw = payload.get("snippets")
    if isinstance(snippets_raw, str):
        snippets = [snippets_raw.strip()] if snippets_raw.strip() else []
    elif isinstance(snippets_raw, list):
        snippets = [str(item).strip() for item in snippets_raw if str(item).strip()]
    else:
        fallback = str(payload.get("snippet") or payload.get("message") or "").strip()
        snippets = [fallback] if fallback else []

    attachments_raw = payload.get("attachments")
    attachments: list[dict[str, Any]] = []
    if isinstance(attachments_raw, list):
        for item in attachments_raw:
            if isinstance(item, dict):
                attachments.append(
                    {
                        "name": str(item.get("name") or item.get("filename") or "").strip(),
                        "media_type": str(item.get("media_type") or item.get("content_type") or "").strip(),
                        "handoff_ref": str(item.get("handoff_ref") or item.get("id") or "").strip(),
                    }
                )

    title = subject or (snippets[0] if snippets else "Neue Anfrage")
    suggested_actions = [
        {
            "type": "create_task",
            "title": title[:180],
            "due_date": str(payload.get("due_date") or "").strip() or None,
            "project_hint": str(payload.get("project_hint") or "").strip() or None,
            "calendar_hint": str(payload.get("calendar_hint") or "").strip() or None,
            "requires_confirm": True,
            "read_only": True,
        }
    ]
    proposal = build_appointment_proposal(
        lead=title,
        project=payload.get("project_hint"),
        starts_at=payload.get("due_date"),
    )
    if proposal.get("starts_at"):
        suggested_actions.append(proposal)

    return IntakeEnvelope(
        source=source,
        thread_id=thread_id,
        sender=sender,
        subject=subject,
        snippets=snippets,
        attachments=attachments,
        suggested_actions=suggested_actions,
    )


def envelope_from_payload(payload: dict[str, Any]) -> IntakeEnvelope:
    if isinstance(payload.get("suggested_actions"), list):
        return IntakeEnvelope(
            source=str(payload.get("source") or "mail").strip().lower() or "mail",
            thread_id=str(payload.get("thread_id") or "").strip(),
            sender=str(payload.get("sender") or payload.get("from") or "").strip(),
            subject=str(payload.get("subject") or "").strip(),
            snippets=[str(item).strip() for item in payload.get("snippets", []) if str(item).strip()],
            attachments=[item for item in payload.get("attachments", []) if isinstance(item, dict)],
            suggested_actions=[item for item in payload.get("suggested_actions", []) if isinstance(item, dict)],
            requires_confirm=bool(payload.get("requires_confirm", True)),
            created_at=str(payload.get("created_at") or _utc_now()),
        )
    return normalize_intake_payload(payload)
