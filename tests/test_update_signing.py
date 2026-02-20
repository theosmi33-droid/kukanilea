from __future__ import annotations

import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

import app.update as update_mod
from app.update import UpdateError


def _signed_manifest(*, version: str, assets: list[dict]) -> tuple[dict, str]:
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )
    payload = {
        "version": version,
        "release_url": f"https://example.invalid/releases/{version}",
        "generated_at": "2026-02-20T22:00:00Z",
        "assets": assets,
    }
    signature = private_key.sign(update_mod._canonical_json_bytes(payload))
    signature_b64 = base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")
    manifest = {
        **payload,
        "signatures": [{"alg": "ed25519", "key_id": "test-key", "sig": signature_b64}],
    }
    return manifest, public_pem


def test_check_for_installable_update_with_signed_manifest(monkeypatch) -> None:
    manifest, public_pem = _signed_manifest(
        version="1.0.0-beta.3",
        assets=[
            {
                "name": "KUKANILEA-macos.zip",
                "platform": "darwin",
                "url": "https://example.invalid/KUKANILEA-macos.zip",
                "sha256": "a" * 64,
            }
        ],
    )

    def _fake_request_json(url: str, *, timeout_seconds: int):
        assert timeout_seconds == 5
        if url == "https://example.invalid/manifest.json":
            return manifest
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr(update_mod, "_request_json", _fake_request_json)

    result = update_mod.check_for_installable_update(
        "1.0.0-beta.2",
        release_url="https://example.invalid/release-api",
        manifest_url="https://example.invalid/manifest.json",
        timeout_seconds=5,
        platform_name="darwin",
        signing_required=True,
        public_key_pem=public_pem,
    )
    assert result["checked"] is True
    assert result["manifest_used"] is True
    assert result["signature_required"] is True
    assert result["signature_verified"] is True
    assert result["signature_error"] == ""
    assert result["update_available"] is True
    assert result["asset_name"] == "KUKANILEA-macos.zip"
    assert result["sha256"] == "a" * 64


def test_check_for_installable_update_rejects_bad_signature(monkeypatch) -> None:
    manifest, public_pem = _signed_manifest(
        version="1.0.0-beta.3",
        assets=[
            {
                "name": "KUKANILEA-win.zip",
                "platform": "win32",
                "url": "https://example.invalid/KUKANILEA-win.zip",
                "sha256": "b" * 64,
            }
        ],
    )
    manifest["signatures"][0]["sig"] = "AAAA"  # invalid detached signature

    monkeypatch.setattr(update_mod, "_request_json", lambda *args, **kwargs: manifest)

    result = update_mod.check_for_installable_update(
        "1.0.0-beta.2",
        release_url="https://example.invalid/release-api",
        manifest_url="https://example.invalid/manifest.json",
        timeout_seconds=5,
        platform_name="win32",
        signing_required=True,
        public_key_pem=public_pem,
    )
    assert result["manifest_used"] is True
    assert result["signature_verified"] is False
    assert result["error"] == "manifest_signature_invalid"
    assert result["update_available"] is False


def test_check_for_installable_update_manifest_fetch_fallback(monkeypatch) -> None:
    release_payload = {
        "tag_name": "v1.0.0-beta.3",
        "html_url": "https://example.invalid/release",
        "assets": [
            {
                "name": "KUKANILEA-linux.zip",
                "browser_download_url": "https://example.invalid/KUKANILEA-linux.zip",
                "digest": "sha256:" + ("c" * 64),
            }
        ],
    }

    def _fake_request_json(url: str, *, timeout_seconds: int):
        if url == "https://example.invalid/manifest.json":
            raise UpdateError("manifest down", code="request_failed")
        if url == "https://example.invalid/release-api":
            return release_payload
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr(update_mod, "_request_json", _fake_request_json)

    result = update_mod.check_for_installable_update(
        "1.0.0-beta.2",
        release_url="https://example.invalid/release-api",
        manifest_url="https://example.invalid/manifest.json",
        timeout_seconds=5,
        platform_name="linux",
        signing_required=False,
    )
    assert result["manifest_used"] is False
    assert result["checked"] is True
    assert result["update_available"] is True
    assert result["asset_name"] == "KUKANILEA-linux.zip"
    assert result["sha256"] == "c" * 64


def test_check_for_installable_update_manifest_fetch_required(monkeypatch) -> None:
    def _fake_request_json(url: str, *, timeout_seconds: int):
        if url == "https://example.invalid/manifest.json":
            raise UpdateError("manifest down", code="request_failed")
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr(update_mod, "_request_json", _fake_request_json)
    result = update_mod.check_for_installable_update(
        "1.0.0-beta.2",
        release_url="https://example.invalid/release-api",
        manifest_url="https://example.invalid/manifest.json",
        timeout_seconds=5,
        platform_name="linux",
        signing_required=True,
    )
    assert result["checked"] is False
    assert result["error"] == "manifest_fetch_failed"
