from __future__ import annotations

from app.security.gates import confirm_gate, detect_injection, scan_payload_for_injection


def test_confirm_gate_normalizes_case_and_whitespace():
    assert confirm_gate(" yes ") is True
    assert confirm_gate(" TRUE") is True
    assert confirm_gate("1") is True


def test_confirm_gate_rejects_unknown_tokens():
    assert confirm_gate("ok") is False
    assert confirm_gate("0") is False


def test_detect_injection_finds_script_and_sql_patterns():
    assert detect_injection("<script>alert(1)</script>") is not None
    assert detect_injection("'; DROP TABLE users; --") is not None


def test_scan_payload_for_injection_returns_first_finding():
    payload = {"username": "admin", "tenant_id": "x'; DROP TABLE users; --"}
    finding = scan_payload_for_injection(payload, ("username", "tenant_id"))
    assert finding is not None
    assert finding.field == "tenant_id"
