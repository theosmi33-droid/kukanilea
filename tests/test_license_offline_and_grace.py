from __future__ import annotations

import importlib.util
import json
import sys
import uuid
from datetime import date, timedelta
from pathlib import Path

import app.license as license_mod


def _load_stub_module():
    module_path = Path(__file__).parent / "stubs" / "license_server_stub.py"
    module_name = f"license_server_stub_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _valid_license_info(*, payload_hash: str = "hash-1") -> dict:
    return {
        "valid": True,
        "reason": "ok",
        "plan": "PRO",
        "expired": False,
        "device_mismatch": False,
        "payload_hash": payload_hash,
        "payload": {
            "customer_id": "customer-1",
            "plan": "PRO",
            "issued": date.today().isoformat(),
            "expiry": (date.today() + timedelta(days=365)).isoformat(),
            "signature": "dummy",
        },
    }


def test_online_validation_with_local_stub_updates_cache(
    tmp_path: Path, monkeypatch
) -> None:
    stub_mod = _load_stub_module()
    config = stub_mod.StubConfig(
        valid=True,
        tier="enterprise",
        valid_until=(date.today() + timedelta(days=365)).isoformat(),
        reason="ok",
    )
    stub = stub_mod.LicenseServerStub(config)
    base = stub.start()
    try:
        monkeypatch.setattr(
            license_mod, "load_license", lambda _: _valid_license_info()
        )
        state = license_mod.load_runtime_license_state(
            license_path=tmp_path / "license.json",
            trial_path=tmp_path / "trial.json",
            cache_path=tmp_path / "license_cache.json",
            validate_url=f"{base}/api/v1/validate",
            validate_interval_days=30,
            grace_days=30,
        )
    finally:
        stub.stop()

    assert state["read_only"] is False
    assert state["validated_online"] is True
    assert state["plan"] == "enterprise"
    cache = json.loads((tmp_path / "license_cache.json").read_text(encoding="utf-8"))
    assert cache["status"] == "active"


def test_online_validation_with_local_stub_revoked_blocks_instance(
    tmp_path: Path, monkeypatch
) -> None:
    stub_mod = _load_stub_module()
    config = stub_mod.StubConfig(valid=False, tier="", valid_until="", reason="revoked")
    stub = stub_mod.LicenseServerStub(config)
    base = stub.start()
    try:
        monkeypatch.setattr(
            license_mod, "load_license", lambda _: _valid_license_info()
        )
        state = license_mod.load_runtime_license_state(
            license_path=tmp_path / "license.json",
            trial_path=tmp_path / "trial.json",
            cache_path=tmp_path / "license_cache.json",
            validate_url=f"{base}/api/v1/validate",
            validate_interval_days=30,
            grace_days=30,
        )
    finally:
        stub.stop()

    assert state["read_only"] is True
    assert state["reason"] == "revoked"


def test_offline_validation_uses_grace_window(tmp_path: Path, monkeypatch) -> None:
    cache_path = tmp_path / "license_cache.json"
    cache_path.write_text(
        json.dumps(
            {
                "license_hash": "hash-1",
                "status": "active",
                "reason": "ok",
                "last_validated": (date.today() - timedelta(days=45)).isoformat(),
                "grace_expires": (date.today() + timedelta(days=4)).isoformat(),
                "plan": "PRO",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(license_mod, "load_license", lambda _: _valid_license_info())

    # Port 9 is intentionally unreachable in this test context.
    state = license_mod.load_runtime_license_state(
        license_path=tmp_path / "license.json",
        trial_path=tmp_path / "trial.json",
        cache_path=cache_path,
        validate_url="http://127.0.0.1:9/api/v1/validate",
        validate_interval_days=30,
        grace_days=30,
    )

    assert state["read_only"] is False
    assert state["grace_active"] is True
    assert state["reason"] == "license_grace_offline"
