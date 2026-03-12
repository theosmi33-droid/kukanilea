from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_LICENSE_STATE_PATH = Path(__file__).resolve().parents[2] / "app" / "license_state.py"
_LICENSE_SPEC = importlib.util.spec_from_file_location("license_state", _LICENSE_STATE_PATH)
assert _LICENSE_SPEC and _LICENSE_SPEC.loader
_LICENSE_MODULE = importlib.util.module_from_spec(_LICENSE_SPEC)
sys.modules[_LICENSE_SPEC.name] = _LICENSE_MODULE
_LICENSE_SPEC.loader.exec_module(_LICENSE_MODULE)

LicenseInputs = _LICENSE_MODULE.LicenseInputs
evaluate_license_state = _LICENSE_MODULE.evaluate_license_state
normalize_status_hint = _LICENSE_MODULE.normalize_status_hint


def test_normalize_status_accepts_german_variants() -> None:
    assert normalize_status_hint("aktiv") == "active"
    assert normalize_status_hint("gesperrt") == "blocked"
    assert normalize_status_hint("locked") == "blocked"
    assert normalize_status_hint("recovery") == "recover"


def test_active_state_is_writable() -> None:
    out = evaluate_license_state(LicenseInputs(valid=True, expired=False, device_mismatch=False, status_hint="active"))
    assert out["status"] == "active"
    assert out["read_only"] is False


def test_grace_state_is_read_only_fallback() -> None:
    out = evaluate_license_state(LicenseInputs(valid=True, expired=False, device_mismatch=False, status_hint="grace"))
    assert out["status"] == "grace"
    assert out["read_only"] is True
    assert out["reason"] == "grace_read_only"


def test_invalid_license_fails_closed() -> None:
    out = evaluate_license_state(LicenseInputs(valid=False, expired=False, device_mismatch=False, status_hint="active"))
    assert out["status"] == "blocked"
    assert out["read_only"] is True
    assert out["reason"] == "license_invalid"


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
    assert out["transition"] == "blocked->recover"


def test_recover_to_active_when_smb_available() -> None:
    out = evaluate_license_state(
        LicenseInputs(valid=True, expired=False, device_mismatch=False, status_hint="recover", smb_reachable=True)
    )
    assert out["status"] == "active"
    assert out["reason"] == "recovered"
    assert out["transition"] == "recover->active"


def test_recover_waits_in_read_only_when_smb_unavailable() -> None:
    out = evaluate_license_state(
        LicenseInputs(valid=True, expired=False, device_mismatch=False, status_hint="recover", smb_reachable=False)
    )
    assert out["status"] == "recover"
    assert out["read_only"] is True
    assert out["reason"] == "recover_waiting_smb"
    assert out["transition"] == "recover->recover"


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
