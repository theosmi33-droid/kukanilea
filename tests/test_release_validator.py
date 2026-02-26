import base64
import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.core.release_validator import ReleaseValidator


@pytest.fixture
def keys():
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()
    pub_hex = pub.public_bytes_raw().hex()
    return priv, pub_hex


def test_verify_manifest_valid(tmp_path, keys):
    priv, pub_hex = keys
    manifest_path = tmp_path / "manifest.json"

    payload = {"version": "1.6.7", "files": {"test.txt": "some-hash"}}

    # Canonicalize
    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )
    signature = priv.sign(payload_bytes)

    payload["signature"] = base64.b64encode(signature).decode("utf-8")

    with open(manifest_path, "w") as f:
        json.dump(payload, f)

    validator = ReleaseValidator(public_key_hex=pub_hex)
    assert validator.verify_manifest(manifest_path) is True


def test_verify_manifest_invalid_signature(tmp_path, keys):
    priv, pub_hex = keys
    manifest_path = tmp_path / "manifest.json"

    payload = {
        "version": "1.6.7",
        "signature": base64.b64encode(b"wrong-signature").decode("utf-8"),
    }

    with open(manifest_path, "w") as f:
        json.dump(payload, f)

    validator = ReleaseValidator(public_key_hex=pub_hex)
    assert validator.verify_manifest(manifest_path) is False


def test_verify_files(tmp_path, keys):
    priv, pub_hex = keys
    root_dir = tmp_path / "app"
    root_dir.mkdir()

    test_file = root_dir / "test.txt"
    test_file.write_text("hello world")

    import hashlib

    file_hash = hashlib.sha256(b"hello world").hexdigest()

    manifest_path = tmp_path / "manifest.json"
    payload = {"version": "1.6.7", "files": {"test.txt": file_hash}}

    validator = ReleaseValidator(public_key_hex=pub_hex)
    with open(manifest_path, "w") as f:
        json.dump(payload, f)

    assert validator.verify_files(manifest_path, root_dir) is True

    # Mismatch
    test_file.write_text("corrupted")
    assert validator.verify_files(manifest_path, root_dir) is False
