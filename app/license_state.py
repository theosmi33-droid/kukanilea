from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class LicenseInputs:
    valid: bool
    expired: bool
    device_mismatch: bool
    status_hint: str
    smb_reachable: bool = True


def normalize_status_hint(value: Any) -> str:
    raw = str(value or "active").strip().lower()
    if raw in {"active", "aktiv"}:
        return "active"
    if raw in {"blocked", "gesperrt", "locked", "suspended"}:
        return "blocked"
    if raw in {"grace", "grace_period", "kulanz"}:
        return "grace"
    if raw in {"recover", "recovery", "wiederherstellung"}:
        return "recover"
    return "active"


def evaluate_license_state(inputs: LicenseInputs) -> Dict[str, Any]:
    """License state machine: active -> grace -> blocked -> recover."""
    if not inputs.valid:
        return {
            "status": "blocked",
            "read_only": True,
            "reason": "license_invalid",
            "transition": "boot->blocked",
        }

    normalized = normalize_status_hint(inputs.status_hint)

    if inputs.device_mismatch:
        return {
            "status": "blocked",
            "read_only": True,
            "reason": "device_mismatch",
            "transition": "*->blocked",
        }

    if inputs.expired:
        return {
            "status": "blocked",
            "read_only": True,
            "reason": "license_expired",
            "transition": f"{normalized}->blocked",
        }

    if normalized == "blocked":
        if inputs.smb_reachable:
            return {
                "status": "recover",
                "read_only": True,
                "reason": "recover_pending",
                "transition": "blocked->recover",
            }
        return {
            "status": "blocked",
            "read_only": True,
            "reason": "license_blocked_smb_unreachable",
            "transition": "blocked->blocked",
        }

    if normalized == "recover":
        if inputs.smb_reachable:
            return {
                "status": "active",
                "read_only": False,
                "reason": "recovered",
                "transition": "recover->active",
            }
        return {
            "status": "recover",
            "read_only": True,
            "reason": "recover_waiting_smb",
            "transition": "recover->recover",
        }

    if normalized == "grace":
        return {
            "status": "grace",
            "read_only": True,
            "reason": "grace_read_only",
            "transition": "active->grace",
        }

    return {
        "status": "active",
        "read_only": False,
        "reason": "ok",
        "transition": "steady_active",
    }
