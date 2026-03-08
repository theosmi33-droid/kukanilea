from __future__ import annotations

import app.contracts.tool_contracts as contracts


def test_normalization_missing_kind_marks_degraded_and_fills_summary_kind() -> None:
    payload = {
        "tool": "mail",
        "status": "ok",
        "updated_at": "2026-03-05T00:00:00Z",
        "metrics": {},
        "details": {
            "tenant": "default",
            "contract": {
                "version": "2026-03-05",
                "read_only": False,
            },
        },
    }

    normalized, errors = contracts._normalize_contract_payload(payload, "mail", contract_kind="summary")

    assert "missing:details.contract.kind" in errors
    assert normalized["status"] == "degraded"
    assert normalized["degraded_reason"] == "contract_normalized"
    assert normalized["details"]["contract"]["kind"] == "summary"
    assert normalized["details"]["normalization"]["applied"] is True


def test_normalization_tenant_mismatch_corrects_scope() -> None:
    payload = {
        "tool": "mail",
        "status": "ok",
        "updated_at": "2026-03-05T00:00:00Z",
        "metrics": {},
        "details": {
            "tenant": "wrong-tenant",
            "contract": {
                "version": "2026-03-05",
                "read_only": False,
                "kind": "summary",
            },
        },
    }

    normalized, _ = contracts._normalize_contract_payload(
        payload,
        "mail",
        tenant="correct-tenant",
        contract_kind="summary",
    )

    assert normalized["status"] == "degraded"
    assert normalized["degraded_reason"] == "tenant_scope_corrected"
    assert normalized["details"]["tenant"] == "correct-tenant"
    assert "tenant_scope_mismatch" in normalized["details"]["normalization"]["issues"]


def test_normalization_with_shape_errors_preserves_contract_normalized_reason_even_with_tenant_fix() -> None:
    payload = {
        "tool": "mail",
        "status": "ok",
        "updated_at": "2026-03-05T00:00:00Z",
        "metrics": {},
        "details": {
            "tenant": "wrong-tenant",
            "contract": {
                "version": "2026-03-05",
                "read_only": False,
            },
        },
    }

    normalized, errors = contracts._normalize_contract_payload(payload, "mail", tenant="KUKANILEA")

    assert "missing:details.contract.kind" in errors
    assert normalized["status"] == "degraded"
    assert normalized["degraded_reason"] == "contract_normalized"
    assert normalized["details"]["tenant"] == "KUKANILEA"
    assert "tenant_scope_mismatch" in normalized["details"]["normalization"]["issues"]


def test_validate_summary_health_pair_consistency() -> None:
    summary = {
        "tool": "mail",
        "status": "ok",
        "details": {
            "tenant": "t1",
            "contract": {"version": "v1", "read_only": False, "kind": "summary"},
        },
    }
    health = {
        "tool": "mail",
        "status": "ok",
        "details": {
            "tenant": "t2",
            "contract": {"version": "v1", "read_only": False, "kind": "health"},
            "checks": {"summary_contract": True, "backend_ready": True, "offline_safe": True},
        },
    }
    errors = contracts.validate_summary_health_pair(summary, health)
    assert "mismatch:tenant" in errors


def test_validate_summary_health_pair_version_mismatch() -> None:
    summary = {
        "tool": "mail",
        "status": "ok",
        "details": {
            "tenant": "t1",
            "contract": {"version": "v1", "read_only": False, "kind": "summary"},
        },
    }
    health = {
        "tool": "mail",
        "status": "ok",
        "details": {
            "tenant": "t1",
            "contract": {"version": "v2", "read_only": False, "kind": "health"},
            "checks": {"summary_contract": True, "backend_ready": True, "offline_safe": True},
        },
    }
    errors = contracts.validate_summary_health_pair(summary, health)
    assert "mismatch:contract.version" in errors
