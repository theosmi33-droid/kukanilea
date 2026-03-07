from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Iterable

MAIL_CATEGORIES = ("request", "invoice", "spam", "follow_up")


@dataclass(frozen=True)
class TriageResult:
    category: str
    confidence: float
    reason: str


def _to_text(value: object) -> str:
    return str(value or "").strip().lower()


def classify_message(message: dict | None) -> TriageResult:
    payload = message or {}
    text = " ".join(
        _to_text(payload.get(key))
        for key in ("subject", "body", "snippet", "from")
    )

    keyword_sets: list[tuple[str, tuple[str, ...], str]] = [
        ("spam", ("gewinnspiel", "lotterie", "bitcoin", "casino", "viagra", "free money", "klicken sie hier"), "spam_keywords"),
        ("invoice", ("rechnung", "invoice", "zahlungsziel", "fällig", "iban", "mahnung"), "invoice_keywords"),
        ("follow_up", ("erinnerung", "nachfassen", "follow up", "statusupdate", "rückmeldung ausstehend"), "follow_up_keywords"),
        ("request", ("anfrage", "angebot", "quote", "rabatt", "preis", "offerte", "hilfe", "support"), "request_keywords"),
    ]

    for category, words, reason in keyword_sets:
        if any(word in text for word in words):
            return TriageResult(category=category, confidence=0.9, reason=reason)

    return TriageResult(category="request", confidence=0.35, reason="fallback_request")


def build_attachment_handover(message: dict | None) -> dict[str, Any]:
    attachments_raw = (message or {}).get("attachments")
    attachments = attachments_raw if isinstance(attachments_raw, list) else []
    normalized: list[dict[str, Any]] = []
    for idx, item in enumerate(attachments, start=1):
        if not isinstance(item, dict):
            continue
        attachment_id = str(item.get("id") or item.get("upload_id") or f"att-{idx}").strip() or f"att-{idx}"
        normalized.append(
            {
                "id": attachment_id,
                "filename": str(item.get("filename") or item.get("name") or "").strip(),
                "mime_type": str(item.get("mime_type") or "application/octet-stream"),
                "source": str(item.get("source") or "mail_attachment"),
                "forward_to": "upload_dms",
            }
        )
    return {
        "target": "upload_dms",
        "ready": bool(normalized),
        "count": len(normalized),
        "items": normalized,
    }


def generate_reply_draft(message: dict | None, *, read_only_default: bool = True, external_api_enabled: bool = False) -> dict:
    triage = classify_message(message)
    sender = str((message or {}).get("from") or "Kontakt")

    templates = {
        "request": "Vielen Dank für Ihre Anfrage. Wir prüfen Ihr Anliegen intern und senden Ihnen die nächsten Schritte.",
        "invoice": "Vielen Dank für die Zusendung. Wir prüfen die Rechnung und melden uns bei Rückfragen.",
        "spam": "Diese Nachricht wurde als potenzieller Spam markiert und wird nicht automatisch beantwortet.",
        "follow_up": "Vielen Dank für die Erinnerung. Wir priorisieren die Folgeaktion und melden uns zeitnah mit einem Status.",
    }
    subject_prefix = {
        "request": "Rückmeldung zur Anfrage",
        "invoice": "Rückmeldung zur Rechnung",
        "spam": "Interner Hinweis: Spam-Prüfung",
        "follow_up": "Rückmeldung zur Folgeaktion",
    }
    handover = build_attachment_handover(message)

    return {
        "status": "draft_created",
        "triage": triage.__dict__,
        "subject": f"{subject_prefix[triage.category]} - {sender}",
        "body": templates[triage.category],
        "read_only": bool(read_only_default),
        "confirm_required": True,
        "send_allowed": False,
        "external_api_used": False,
        "external_api_enabled": bool(external_api_enabled),
        "attachment_handover": handover,
    }


def _parse_iso8601(value: str) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def sla_unanswered_alert(messages: Iterable[dict], *, threshold_hours: int = 24, now: datetime | None = None) -> dict:
    now_utc = now.astimezone(UTC) if now else datetime.now(UTC)
    overdue = 0
    inspected = 0
    for msg in messages:
        inspected += 1
        if bool(msg.get("answered")):
            continue
        received_at = _parse_iso8601(str(msg.get("received_at") or ""))
        if received_at is None:
            continue
        age_hours = (now_utc - received_at).total_seconds() / 3600
        if age_hours > threshold_hours:
            overdue += 1

    return {
        "metric": "unanswered_gt_threshold_hours",
        "threshold_hours": int(threshold_hours),
        "inspected": inspected,
        "alerts": overdue,
    }
