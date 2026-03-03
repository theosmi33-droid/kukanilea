from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Tuple

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from app.config import Config

logger = logging.getLogger("kukanilea.mesh_identity")

HANDSHAKE_INIT_PURPOSE = "mesh_handshake_init"
HANDSHAKE_ACK_PURPOSE = "mesh_handshake_ack"
DEFAULT_HANDSHAKE_MAX_AGE_SECONDS = 120


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _parse_utc(ts: str) -> Optional[datetime]:
    text = str(ts or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def get_identity_paths() -> Tuple[Path, Path]:
    root = Config.USER_DATA_ROOT
    priv_path = root / "mesh_id.priv"
    pub_path = root / "mesh_id.pub"
    return priv_path, pub_path


def compute_node_id(public_key_b64: str) -> str:
    try:
        pub_raw = base64.b64decode(public_key_b64, validate=True)
    except Exception as exc:
        raise ValueError("invalid_public_key") from exc

    digest = hashlib.sha256(pub_raw).hexdigest()[:16].upper()
    return f"HUB-{digest}"


def ensure_mesh_identity() -> Tuple[str, str]:
    """
    Ensures that the Hub has a unique Ed25519 identity.
    Returns (public_key_b64, node_id).
    """
    priv_path, pub_path = get_identity_paths()

    if priv_path.exists() and pub_path.exists():
        try:
            pub_key_b64 = pub_path.read_text(encoding="utf-8").strip()
            node_id = compute_node_id(pub_key_b64)
            return pub_key_b64, node_id
        except Exception as e:
            logger.error(f"Failed to load mesh identity: {e}")

    logger.info("Generating new Mesh Identity keypair...")
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    priv_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.OpenSSH,
        encryption_algorithm=serialization.NoEncryption(),
    )

    pub_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    pub_b64 = base64.b64encode(pub_bytes).decode("utf-8")

    priv_path.parent.mkdir(parents=True, exist_ok=True)
    priv_path.write_bytes(priv_bytes)
    pub_path.write_text(pub_b64, encoding="utf-8")

    try:
        os.chmod(priv_path, 0o600)
    except OSError:
        pass

    try:
        os.chmod(pub_path, 0o644)
    except OSError:
        pass

    node_id = compute_node_id(pub_b64)
    return pub_b64, node_id


def sign_message(message: bytes) -> str:
    """Signs a message using the local private key."""
    priv_path, _ = get_identity_paths()
    if not priv_path.exists():
        raise RuntimeError("Mesh identity not initialized")

    priv_bytes = priv_path.read_bytes()
    private_key = serialization.load_ssh_private_key(priv_bytes, password=None)

    if not isinstance(private_key, ed25519.Ed25519PrivateKey):
        raise TypeError("Not an Ed25519 private key")

    sig = private_key.sign(message)
    return base64.b64encode(sig).decode("utf-8")


def verify_signature(public_key_b64: str, message: bytes, signature_b64: str) -> bool:
    """Verifies a signature from a peer Hub."""
    try:
        pub_bytes = base64.b64decode(public_key_b64, validate=True)
        sig_bytes = base64.b64decode(signature_b64, validate=True)

        public_key = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)
        public_key.verify(sig_bytes, message)
        return True
    except Exception as e:
        logger.error(f"Signature verification failed: {e}")
        return False


def create_handshake_envelope(
    *,
    name: str,
    purpose: str,
    challenge: Optional[str] = None,
) -> dict[str, Any]:
    """
    Creates a signed handshake envelope with freshness + anti-replay fields.
    """
    pub_key, node_id = ensure_mesh_identity()
    nonce = secrets.token_urlsafe(24)

    data: dict[str, Any] = {
        "purpose": purpose,
        "node_id": node_id,
        "name": str(name or "KUKANILEA Hub"),
        "public_key": pub_key,
        "nonce": nonce,
        "timestamp": _now_iso(),
    }
    if challenge:
        data["challenge"] = str(challenge)

    signature = sign_message(_canonical_json_bytes(data))
    return {"data": data, "signature": signature, "algorithm": "ed25519"}


def verify_handshake_envelope(
    envelope: Mapping[str, Any],
    *,
    expected_purpose: str,
    expected_challenge: Optional[str] = None,
    max_age_seconds: int = DEFAULT_HANDSHAKE_MAX_AGE_SECONDS,
) -> tuple[bool, str, Optional[dict[str, Any]]]:
    """
    Verifies signed handshake envelopes for both init and ack packets.
    Returns (ok, reason, parsed_data).
    """
    try:
        data_obj = envelope.get("data")
        if not isinstance(data_obj, dict):
            legacy_peer = envelope.get("peer")
            if isinstance(legacy_peer, dict):
                data_obj = legacy_peer
            else:
                return False, "missing_data", None

        signature = str(envelope.get("signature") or "")
        if not signature:
            return False, "missing_signature", None

        required = ["purpose", "node_id", "name", "public_key", "nonce", "timestamp"]
        missing = [k for k in required if not data_obj.get(k)]
        if missing:
            return False, f"missing_fields:{','.join(missing)}", None

        purpose = str(data_obj.get("purpose"))
        if purpose != expected_purpose:
            return False, "invalid_purpose", None

        if expected_challenge is not None and str(data_obj.get("challenge") or "") != str(
            expected_challenge
        ):
            return False, "challenge_mismatch", None

        public_key_b64 = str(data_obj.get("public_key") or "")
        expected_node = compute_node_id(public_key_b64)
        if str(data_obj.get("node_id") or "") != expected_node:
            return False, "node_key_mismatch", None

        if not verify_signature(public_key_b64, _canonical_json_bytes(data_obj), signature):
            return False, "invalid_signature", None

        ts = _parse_utc(str(data_obj.get("timestamp") or ""))
        if ts is None:
            return False, "invalid_timestamp", None

        age_seconds = abs((datetime.now(timezone.utc) - ts).total_seconds())
        if age_seconds > max_age_seconds:
            return False, "stale_timestamp", None
        return True, "ok", dict(data_obj)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        logger.warning("Invalid mesh envelope: %s", exc)
        return False, "invalid_envelope", None
