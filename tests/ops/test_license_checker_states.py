from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from nacl.signing import SigningKey

from app.core.license_checker import check_license_file


def _write_signed(tmp_path, payload):
    sk = SigningKey.generate()
    body = dict(payload)
    message = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    body["signature"] = sk.sign(message).signature.hex()
    lic = tmp_path / "license.json"
    lic.write_text(json.dumps(body), encoding="utf-8")
    return lic, sk.verify_key.encode().hex()


def test_license_ok(monkeypatch, tmp_path):
    valid_until = (datetime.now(timezone.utc) + timedelta(days=2)).strftime("%Y-%m-%d")
    lic, pub = _write_signed(tmp_path, {"tenant_id": "T1", "valid_until": valid_until})
    monkeypatch.setenv("TEST_PUB", pub)
    assert check_license_file(str(lic), "TEST_PUB")["status"] == "OK"


def test_license_warn_grace(monkeypatch, tmp_path):
    expired = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    lic, pub = _write_signed(tmp_path, {"tenant_id": "T1", "valid_until": expired})
    monkeypatch.setenv("TEST_PUB", pub)
    monkeypatch.setenv("LICENSE_GRACE_DAYS", "3")
    assert check_license_file(str(lic), "TEST_PUB")["status"] == "WARN"


def test_license_locked_when_missing(tmp_path):
    assert check_license_file(str(tmp_path / "missing.json"), "ANY")["status"] == "LOCK"


def test_license_locked_when_pubkey_missing(tmp_path):
    valid_until = (datetime.now(timezone.utc) + timedelta(days=2)).strftime("%Y-%m-%d")
    lic, _pub = _write_signed(tmp_path, {"tenant_id": "T1", "valid_until": valid_until})
    result = check_license_file(str(lic), "UNSET_PUB")
    assert result["status"] == "LOCK"
    assert result["reason"] == "MISSING_PUBLIC_KEY"


def test_license_locked_when_invalid_json(tmp_path):
    lic = tmp_path / "license.json"
    lic.write_text("{broken", encoding="utf-8")
    result = check_license_file(str(lic), "UNSET_PUB")
    assert result["status"] == "LOCK"
    assert result["reason"] == "INVALID_LICENSE_FILE"
