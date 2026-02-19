from __future__ import annotations

import json

from app.automation.runner import _build_context


def test_build_context_extracts_safe_ids_only() -> None:
    event_row = {
        "id": 42,
        "ts": "2026-02-19T10:00:00Z",
        "event_type": "mailbox_message_received",
        "entity_type": "mailbox_thread",
        "entity_id": 77,
        "payload_json": json.dumps(
            {
                "tenant_id": "TENANT_A",
                "thread_id": "th-1",
                "account_id": "acc-2",
                "task_status": "RESOLVED",
                "subject": "secret",
                "from_email": "user@example.com",
                "data": {
                    "source_kind": "document",
                    "action": "ingest_ok",
                    "intent": "quote_request",
                },
            }
        ),
    }
    context = _build_context(
        tenant_id="TENANT_A",
        event_row=event_row,
        trigger_ref="eventlog:42",
    )

    assert context["event_id"] == "42"
    assert context["thread_id"] == "th-1"
    assert context["account_id"] == "acc-2"
    assert context["source_kind"] == "document"
    assert context["source_action"] == "ingest_ok"
    assert context["intent"] == "quote_request"
    assert context["task_status"] == "RESOLVED"
    assert "subject" not in context
    assert "from_email" not in context
