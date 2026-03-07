from __future__ import annotations

from kukanilea.orchestrator.audit_schema import (
    REQUIRED_AUDIT_FIELDS,
    build_audit_event,
    has_required_audit_fields,
)


def test_has_required_audit_fields_rejects_none_values() -> None:
    payload = {field: "ok" for field in REQUIRED_AUDIT_FIELDS}
    payload["reason"] = None

    assert has_required_audit_fields(payload) is False


def test_build_audit_event_produces_required_fields() -> None:
    event = build_audit_event(
        "intent_detected",
        tenant="tenant-1",
        user="user-1",
        action="dashboard.summary.read",
        tool="dashboard",
        intent="dashboard_status",
        risk="low",
        execution_mode="read",
        status="detected",
        reason="intent_classified",
        meta={"x": "y"},
    )

    assert has_required_audit_fields(event) is True
