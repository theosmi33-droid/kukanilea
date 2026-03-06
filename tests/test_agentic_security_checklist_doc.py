from __future__ import annotations

from pathlib import Path

DOC = Path("docs/testing/agentic_security_checklist_and_testplan.md")


def _read() -> str:
    assert DOC.exists(), f"missing: {DOC}"
    return DOC.read_text(encoding="utf-8")


def test_security_checklist_doc_exists() -> None:
    assert DOC.exists()


def test_security_checklist_contains_core_guardrail_table() -> None:
    text = _read()
    assert "## Security Checklist & Test Plan" in text
    assert "| Guardrail |" in text


def test_security_checklist_covers_expected_controls() -> None:
    text = _read()
    required_controls = [
        "Never show raw errors",
        "Validate redirects allowlist",
        "Rate limit password reset",
        "Server-side permission checks",
        "CORS not wide open",
        "Session expiration + refresh rotation",
    ]
    for control in required_controls:
        assert control in text


def test_security_checklist_has_ci_requirements() -> None:
    text = _read()
    assert "## Must-have in CI" in text
    assert "Security unit suite is mandatory" in text


def test_security_checklist_has_evidence_mapping_section() -> None:
    text = _read()
    assert "## Evidence Mapping" in text
    assert "Required proof artifact" in text
    assert "Verification command" in text


def test_security_checklist_has_threat_scenarios() -> None:
    text = _read()
    assert "## Minimal Threat Scenarios" in text
    for marker in [
        "Prompt injection via upload",
        "Cross-tenant task creation",
        "Webhook replay",
        "Session fixation",
        "Brute-force password reset",
        "Unsafe redirect exfiltration",
    ]:
        assert marker in text


def test_security_checklist_defines_secure_merge_contract() -> None:
    text = _read()
    assert "## Definition of Secure Merge" in text
    assert "State-changing endpoints" in text


def test_security_checklist_provides_command_bundle() -> None:
    text = _read()
    assert "## Appendix: Practical Command Bundle" in text
    assert "./scripts/ops/security_gate.sh" in text


def test_security_checklist_contains_review_cadence() -> None:
    text = _read()
    assert "## Review Cadence" in text
    cadence_points = [
        "Per PR",
        "Weekly",
        "Release",
        "Quarterly",
    ]
    for point in cadence_points:
        assert point in text


def test_security_checklist_evidence_mapping_lists_core_gates() -> None:
    text = _read()
    expected_rows = [
        "Raw error masking",
        "Redirect allowlist",
        "Password-reset rate limit",
        "Session rotation",
        "AuthZ server-side",
        "Dependency hygiene",
    ]
    for row in expected_rows:
        assert row in text
