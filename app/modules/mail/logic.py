from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Iterable

MAIL_CATEGORIES = ("urgent", "offer", "appointment", "invoice")


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
        ("invoice", ("rechnung", "invoice", "zahlungsziel", "fällig", "iban"), "invoice_keywords"),
        ("appointment", ("termin", "meeting", "kalender", "verschieben", "uhr"), "appointment_keywords"),
        ("offer", ("angebot", "quote", "rabatt", "preis", "offerte"), "offer_keywords"),
        ("urgent", ("dringend", "asap", "sofort", "urgent", "eilt"), "urgent_keywords"),
    ]

    for category, words, reason in keyword_sets:
        if any(word in text for word in words):
            return TriageResult(category=category, confidence=0.9, reason=reason)

    return TriageResult(category="offer", confidence=0.3, reason="fallback_offer")


def generate_reply_draft(message: dict | None, *, read_only_default: bool = True, external_api_enabled: bool = False) -> dict:
    triage = classify_message(message)
    sender = str((message or {}).get("from") or "Kontakt")

    templates = {
        "urgent": "Vielen Dank für Ihre Nachricht. Wir priorisieren Ihr Anliegen und melden uns kurzfristig mit einem konkreten Update.",
        "offer": "Vielen Dank für Ihre Anfrage. Wir prüfen das Angebot intern und senden Ihnen eine Rückmeldung mit den nächsten Schritten.",
        "appointment": "Vielen Dank für die Termin-Nachricht. Wir bestätigen Ihnen zeitnah einen passenden Termin.",
        "invoice": "Vielen Dank für die Zusendung. Wir prüfen die Rechnung und melden uns bei Rückfragen.",
    }
    subject_prefix = {
        "urgent": "Priorisierte Rückmeldung",
        "offer": "Rückmeldung zum Angebot",
        "appointment": "Rückmeldung zum Termin",
        "invoice": "Rückmeldung zur Rechnung",
    }

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
