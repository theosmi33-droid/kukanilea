from __future__ import annotations

import pytest

from app.license_state import LicenseInputs, evaluate_license_state, normalize_status_hint


def test_normalize_status_accepts_german_variants() -> None:
    assert normalize_status_hint("aktiv") == "active"
    assert normalize_status_hint("gesperrt") == "blocked"
    assert normalize_status_hint("locked") == "blocked"
    assert normalize_status_hint("recovery") == "recover"


@pytest.mark.parametrize(
    "status_hint,smb_reachable,expected_status,expected_read_only,expected_transition",
    [
        ("active", True, "active", False, "active->active"),
        ("grace", False, "grace", False, "grace->grace"),
        ("blocked", False, "blocked", True, "blocked->blocked"),
        ("blocked", True, "recover", True, "blocked->recover"),
        ("recover", True, "active", False, "recover->active"),
        ("locked", True, "recover", True, "blocked->recover"),
        ("recovery", True, "active", False, "recover->active"),
    ],
)
def test_license_state_matrix_is_documented_and_testable(
    status_hint: str,
    smb_reachable: bool,
    expected_status: str,
    expected_read_only: bool,
    expected_transition: str,
) -> None:
    """Dokumentiert die SOLL-Zustandsmaschine für OPS_RELEASE Evidence."""
    out = evaluate_license_state(
        LicenseInputs(valid=True, expired=False, device_mismatch=False, status_hint=status_hint, smb_reachable=smb_reachable)
    )
    assert out["status"] == expected_status
    assert out["read_only"] is expected_read_only
    assert out["transition"] == expected_transition


def test_blocked_with_smb_unreachable_stays_blocked() -> None:
    out = evaluate_license_state(
        LicenseInputs(valid=True, expired=False, device_mismatch=False, status_hint="blocked", smb_reachable=False)
    )
    assert out["status"] == "blocked"
    assert out["reason"] == "license_blocked_smb_unreachable"


def test_recover_to_active_when_smb_available() -> None:
    out = evaluate_license_state(
        LicenseInputs(valid=True, expired=False, device_mismatch=False, status_hint="recover", smb_reachable=True)
    )
    assert out["status"] == "active"
    assert out["reason"] == "recovered"


def test_device_mismatch_forces_blocked() -> None:
    out = evaluate_license_state(
        LicenseInputs(valid=True, expired=False, device_mismatch=True, status_hint="active", smb_reachable=True)
    )
    assert out["status"] == "blocked"
    assert out["read_only"] is True
