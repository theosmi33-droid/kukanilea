from __future__ import annotations

import app.contracts.tool_contracts as contracts


def test_normalize_contract_payload_enforces_requested_tenant_scope() -> None:
    payload = {
        "tool": "tasks",
        "status": "ok",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "metrics": {"tasks_total": 1},
        "details": {
            "tenant": "wrong-tenant",
            "contract": {
                "version": contracts.CONTRACT_VERSION,
                "kind": "summary",
                "read_only": False,
            },
        },
    }

    normalized, errors = contracts._normalize_contract_payload(payload, "tasks", tenant="KUKANILEA")

    assert errors == []
    assert normalized["status"] == "ok"
    assert normalized["details"]["tenant"] == "KUKANILEA"


def test_apply_mia_parity_marks_tools_without_profile_as_degraded() -> None:
    payload = contracts._contract_payload("unknown", "ok", metrics={}, details={"tenant": "KUKANILEA"})
    hardened = contracts._apply_mia_parity(payload, "unknown")

    assert hardened["status"] == "degraded"
    assert hardened["degraded_reason"] == "mia_parity_below_baseline"
    assert hardened["details"]["mia"]["tier"] == "low"


def test_collect_upload_summary_marks_pending_pipeline_degraded(monkeypatch) -> None:
    monkeypatch.setattr(contracts, "_core_get", lambda _name, _default=None: None)

    metrics, details, reason = contracts._collect_upload_summary("KUKANILEA")

    assert reason == "pending_pipeline_unavailable"
    assert metrics["pending_items"] >= 0
    assert details["tenant"] == "KUKANILEA"


def test_collect_tasks_summary_reports_missing_backend(monkeypatch) -> None:
    monkeypatch.setattr(contracts, "_core_get", lambda _name, _default=None: None)

    metrics, details, reason = contracts._collect_tasks_summary("KUKANILEA")

    assert metrics == {"tasks_total": 0, "tasks_open": 0}
    assert details["source"] == "core.task_list"
    assert reason == "tasks_backend_missing"
