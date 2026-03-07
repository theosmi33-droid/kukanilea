from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.modules.mail.contracts import build_health, build_summary
from app.modules.mail.logic import classify_message, generate_reply_draft, sla_unanswered_alert


def test_mail_triage_classifies_invoice_keyword() -> None:
    result = classify_message({"subject": "Rechnung 2026-03", "body": "Bitte bis Freitag zahlen."})
    assert result.category == "invoice"
    assert result.confidence >= 0.8


def test_mail_triage_classifies_follow_up_keyword() -> None:
    result = classify_message({"subject": "Erinnerung", "body": "Bitte kurzes Statusupdate zur offenen Anfrage."})
    assert result.category == "follow_up"


def test_mail_triage_classifies_spam_keyword() -> None:
    result = classify_message({"subject": "Free money bitcoin", "body": "Klicken Sie hier für Casino Bonus."})
    assert result.category == "spam"


def test_mail_draft_generator_enforces_read_only_confirm_gate() -> None:
    draft = generate_reply_draft({"subject": "Bitte Hilfe", "from": "kunde@example.com"})
    assert draft["triage"]["category"] == "request"
    assert draft["read_only"] is True
    assert draft["confirm_required"] is True
    assert draft["send_allowed"] is False
    assert draft["external_api_used"] is False
    assert draft["attachment_handover"]["target"] == "upload_dms"


def test_mail_draft_attachment_handover_collects_normalized_items() -> None:
    draft = generate_reply_draft(
        {
            "subject": "Rechnung und Beleg",
            "from": "kunde@example.com",
            "attachments": [
                {"id": "a-1", "filename": "rechnung.pdf", "mime_type": "application/pdf"},
                {"upload_id": "u-2", "name": "foto.jpg", "source": "inbox"},
            ],
        }
    )

    handover = draft["attachment_handover"]
    assert handover["ready"] is True
    assert handover["count"] == 2
    assert handover["items"][0]["forward_to"] == "upload_dms"


def test_sla_alert_metric_detects_overdue_unanswered() -> None:
    now = datetime(2026, 3, 5, 12, 0, tzinfo=UTC)
    messages = [
        {"received_at": (now - timedelta(hours=26)).isoformat(), "answered": False},
        {"received_at": (now - timedelta(hours=3)).isoformat(), "answered": False},
        {"received_at": (now - timedelta(hours=40)).isoformat(), "answered": True},
    ]
    metric = sla_unanswered_alert(messages, threshold_hours=24, now=now)
    assert metric["alerts"] == 1
    assert metric["threshold_hours"] == 24


def test_mail_summary_and_health_include_sla_metric() -> None:
    now = datetime.now(UTC)
    messages = [{"received_at": (now - timedelta(hours=30)).isoformat(), "answered": False}]
    summary = build_summary("t1", messages=messages, sla_hours=24)
    health, code = build_health("t1", messages=messages, sla_hours=24)

    assert summary["tool"] == "mail"
    assert summary["metrics"]["sla_unanswered_alerts"] == 1
    assert health["details"]["checks"]["confirm_gate"] is True
    assert code == 200
