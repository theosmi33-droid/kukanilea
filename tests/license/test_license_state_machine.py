from __future__ import annotations

from app.license_state import LicenseInputs, evaluate_license_state, normalize_status_hint


def test_normalize_status_accepts_german_variants() -> None:
    assert normalize_status_hint("aktiv") == "active"
    assert normalize_status_hint("gesperrt") == "blocked"
    assert normalize_status_hint("locked") == "blocked"
    assert normalize_status_hint("recovery") == "recover"


def test_active_state_is_writable() -> None:
    out = evaluate_license_state(LicenseInputs(valid=True, expired=False, device_mismatch=False, status_hint="active"))
    assert out["status"] == "active"
    assert out["read_only"] is False


def test_grace_state_remains_writable() -> None:
    out = evaluate_license_state(LicenseInputs(valid=True, expired=False, device_mismatch=False, status_hint="grace"))
    assert out["status"] == "grace"
    assert out["read_only"] is False


def test_blocked_with_smb_unreachable_stays_blocked() -> None:
    out = evaluate_license_state(
        LicenseInputs(valid=True, expired=False, device_mismatch=False, status_hint="blocked", smb_reachable=False)
    )
    assert out["status"] == "blocked"
    assert out["reason"] == "license_blocked_smb_unreachable"


def test_blocked_with_smb_reachable_enters_recover() -> None:
    out = evaluate_license_state(
        LicenseInputs(valid=True, expired=False, device_mismatch=False, status_hint="blocked", smb_reachable=True)
    )
    assert out["status"] == "recover"
    assert out["read_only"] is True


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


def test_locked_alias_behaves_like_blocked() -> None:
    out = evaluate_license_state(
        LicenseInputs(valid=True, expired=False, device_mismatch=False, status_hint="locked", smb_reachable=True)
    )
    assert out["status"] == "recover"
    assert out["transition"] == "blocked->recover"


def test_recovery_alias_returns_to_active() -> None:
    out = evaluate_license_state(
        LicenseInputs(valid=True, expired=False, device_mismatch=False, status_hint="recovery", smb_reachable=True)
    )
    assert out["status"] == "active"
    assert out["reason"] == "recovered"
