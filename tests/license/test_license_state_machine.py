from __future__ import annotations

import importlib.util
import json
import sys
from datetime import date, timedelta
from pathlib import Path


def _load_license_module():
    repo = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("kukanilea_license", repo / "app/license.py")
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_license_state_machine_active_blocked_grace_recovery(tmp_path: Path):
    license_mod = _load_license_module()

    trial = tmp_path / "trial.json"
    state_file = tmp_path / "runtime_state.json"
    license_mod.load_license = lambda _p: {
        "valid": True,
        "plan": "ENTERPRISE",
        "expired": False,
        "device_mismatch": False,
        "status": "active",
    }

    active = license_mod.load_runtime_license_state(
        license_path=tmp_path / "license.json",
        trial_path=trial,
        smb_available=True,
        runtime_state_path=state_file,
    )
    assert active["status"] == "active"
    assert active["read_only"] is False

    grace = license_mod.load_runtime_license_state(
        license_path=tmp_path / "license.json",
        trial_path=trial,
        smb_available=False,
        runtime_state_path=state_file,
    )
    assert grace["status"] == "grace"
    assert grace["reason"] == "license_transport_grace"

    state_file.write_text(
        json.dumps({"last_ok": (date.today() - timedelta(days=10)).isoformat()}),
        encoding="utf-8",
    )
    blocked = license_mod.load_runtime_license_state(
        license_path=tmp_path / "license.json",
        trial_path=trial,
        smb_available=False,
        runtime_state_path=state_file,
        grace_days=3,
    )
    assert blocked["status"] == "blocked"
    assert blocked["read_only"] is True

    recovered = license_mod.load_runtime_license_state(
        license_path=tmp_path / "license.json",
        trial_path=trial,
        smb_available=True,
        runtime_state_path=state_file,
    )
    assert recovered["status"] == "active"
    assert recovered["reason"] == "ok"
