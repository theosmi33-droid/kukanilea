from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import app.license as license_mod


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


def test_online_validation_success_updates_cache(tmp_path: Path, monkeypatch) -> None:
    cache_path = tmp_path / "license_cache.json"
    monkeypatch.setattr(license_mod, "load_license", lambda _: _valid_license_info())
    monkeypatch.setattr(
        license_mod,
        "_validate_license_online",
        lambda **_: {
            "request_ok": True,
            "valid": True,
            "reason": "ok",
            "tier": "ENTERPRISE",
            "valid_until": (date.today() + timedelta(days=365)).isoformat(),
        },
    )

    state = license_mod.load_runtime_license_state(
        license_path=tmp_path / "license.json",
        trial_path=tmp_path / "trial.json",
        cache_path=cache_path,
        validate_url="https://license.example.test/validate",
        validate_interval_days=30,
        grace_days=30,
    )

    assert state["read_only"] is False
    assert state["validated_online"] is True
    assert state["plan"] == "ENTERPRISE"
    assert cache_path.exists()
    cache = json.loads(cache_path.read_text(encoding="utf-8"))
    assert cache["status"] == "active"


def test_online_validation_invalid_blocks_instance(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(license_mod, "load_license", lambda _: _valid_license_info())
    monkeypatch.setattr(
        license_mod,
        "_validate_license_online",
        lambda **_: {
            "request_ok": True,
            "valid": False,
            "reason": "revoked",
        },
    )

    state = license_mod.load_runtime_license_state(
        license_path=tmp_path / "license.json",
        trial_path=tmp_path / "trial.json",
        cache_path=tmp_path / "license_cache.json",
        validate_url="https://license.example.test/validate",
        validate_interval_days=30,
        grace_days=30,
    )

    assert state["read_only"] is True
    assert state["reason"] == "revoked"


def test_online_validation_network_uses_grace_if_available(
    tmp_path: Path, monkeypatch
) -> None:
    cache_path = tmp_path / "license_cache.json"
    cache_path.write_text(
        json.dumps(
            {
                "license_hash": "hash-1",
                "status": "active",
                "reason": "ok",
                "last_validated": (date.today() - timedelta(days=45)).isoformat(),
                "grace_expires": (date.today() + timedelta(days=5)).isoformat(),
                "plan": "PRO",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(license_mod, "load_license", lambda _: _valid_license_info())
    monkeypatch.setattr(
        license_mod,
        "_validate_license_online",
        lambda **_: {
            "request_ok": False,
            "reason": "validation_network_error",
        },
    )

    state = license_mod.load_runtime_license_state(
        license_path=tmp_path / "license.json",
        trial_path=tmp_path / "trial.json",
        cache_path=cache_path,
        validate_url="https://license.example.test/validate",
        validate_interval_days=30,
        grace_days=30,
    )

    assert state["read_only"] is False
    assert state["grace_active"] is True
    assert state["reason"] == "license_grace_offline"


def test_online_validation_network_blocks_after_grace(
    tmp_path: Path, monkeypatch
) -> None:
    cache_path = tmp_path / "license_cache.json"
    cache_path.write_text(
        json.dumps(
            {
                "license_hash": "hash-1",
                "status": "active",
                "reason": "ok",
                "last_validated": (date.today() - timedelta(days=90)).isoformat(),
                "grace_expires": (date.today() - timedelta(days=1)).isoformat(),
                "plan": "PRO",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(license_mod, "load_license", lambda _: _valid_license_info())
    monkeypatch.setattr(
        license_mod,
        "_validate_license_online",
        lambda **_: {
            "request_ok": False,
            "reason": "validation_network_error",
        },
    )

    state = license_mod.load_runtime_license_state(
        license_path=tmp_path / "license.json",
        trial_path=tmp_path / "trial.json",
        cache_path=cache_path,
        validate_url="https://license.example.test/validate",
        validate_interval_days=30,
        grace_days=30,
    )

    assert state["read_only"] is True
    assert state["reason"] == "validation_network_error"
