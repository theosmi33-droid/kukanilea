from __future__ import annotations

import base64
import json
from datetime import date, timedelta
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from app import license as license_mod


def _canonical(payload: dict) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def test_rsa_license_verification(monkeypatch, tmp_path: Path):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    monkeypatch.setenv("KUKANILEA_LICENSE_RSA_PUBLIC_KEY_PEM", public_pem.decode("utf-8"))
    monkeypatch.setattr(license_mod, "device_fingerprint", lambda: "ABCDEF1234567890")

    payload = {
        "customer_id": "tenant-acme",
        "plan": "ENTERPRISE",
        "expiry": (date.today() + timedelta(days=14)).isoformat(),
        "device_fingerprint": "ABCDEF1234567890",
    }
    signature = private_key.sign(
        _canonical(payload),
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
        hashes.SHA256(),
    )
    signed = dict(payload)
    signed["algorithm"] = "RSA_PSS_SHA256"
    signed["signature"] = base64.b64encode(signature).decode("ascii")

    lic_path = tmp_path / "license.json"
    lic_path.write_text(json.dumps(signed), encoding="utf-8")

    parsed = license_mod.load_license(lic_path)
    assert parsed["valid"] is True
    assert parsed["plan"] == "ENTERPRISE"
    assert parsed["device_mismatch"] is False
    assert parsed["algorithm"] == "RSA_PSS_SHA256"


def test_rsa_license_invalid_signature(monkeypatch, tmp_path: Path):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    monkeypatch.setenv("KUKANILEA_LICENSE_RSA_PUBLIC_KEY_PEM", public_pem.decode("utf-8"))

    payload = {
        "customer_id": "tenant-acme",
        "plan": "PRO",
        "expiry": (date.today() + timedelta(days=7)).isoformat(),
    }
    signature = other_key.sign(
        _canonical(payload),
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
        hashes.SHA256(),
    )
    signed = dict(payload)
    signed["algorithm"] = "RSA_PSS_SHA256"
    signed["signature"] = base64.b64encode(signature).decode("ascii")

    lic_path = tmp_path / "license_invalid.json"
    lic_path.write_text(json.dumps(signed), encoding="utf-8")

    parsed = license_mod.load_license(lic_path)
    assert parsed["valid"] is False
    assert parsed["reason"] == "invalid_signature"
