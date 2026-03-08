from __future__ import annotations

import base64
import json
import os
import secrets
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

# Ensure we can import app
sys.path.append(os.getcwd())

from app.config import Config
from app.core.mesh_identity import (
    HANDSHAKE_INIT_PURPOSE,
    compute_node_id,
    ensure_mesh_identity,
    sign_message,
    verify_handshake_envelope,
    verify_signature,
)
from app.core.mesh_network import MeshNetworkManager


def _canonical_bytes(payload: dict) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _build_external_ack(challenge: str) -> dict:
    ext_priv = Ed25519PrivateKey.generate()
    ext_pub_raw = ext_priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    ext_pub_b64 = base64.b64encode(ext_pub_raw).decode("ascii")
    data = {
        "purpose": "mesh_handshake_ack",
        "node_id": compute_node_id(ext_pub_b64),
        "name": "External Hub",
        "public_key": ext_pub_b64,
        "nonce": secrets.token_urlsafe(24),
        "challenge": challenge,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    signature = base64.b64encode(ext_priv.sign(_canonical_bytes(data))).decode("ascii")
    return {"data": data, "signature": signature, "algorithm": "ed25519"}


def _build_external_init(*, challenge: str = "challenge-1", node_id: str | None = None) -> tuple[dict, str]:
    ext_priv = Ed25519PrivateKey.generate()
    ext_pub_raw = ext_priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    ext_pub_b64 = base64.b64encode(ext_pub_raw).decode("ascii")
    data = {
        "purpose": HANDSHAKE_INIT_PURPOSE,
        "node_id": node_id or compute_node_id(ext_pub_b64),
        "name": "External Hub",
        "public_key": ext_pub_b64,
        "nonce": secrets.token_urlsafe(24),
        "challenge": challenge,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    signature = base64.b64encode(ext_priv.sign(_canonical_bytes(data))).decode("ascii")
    return {"data": data, "signature": signature, "algorithm": "ed25519"}, ext_pub_b64


def test_multi_hub_sync():
    print("Testing KUKANILEA Multi-Hub Sync POC...")
    with tempfile.TemporaryDirectory() as tmp_root:
        with patch.object(Config, "USER_DATA_ROOT", Path(tmp_root)):
            with tempfile.NamedTemporaryFile() as tmp:
                db_path = tmp.name
                con = sqlite3.connect(db_path)
                con.execute(
                    """
                    CREATE TABLE mesh_nodes(
                      node_id TEXT PRIMARY KEY,
                      name TEXT NOT NULL,
                      public_key TEXT NOT NULL,
                      last_ip TEXT,
                      last_seen TEXT,
                      status TEXT DEFAULT 'OFFLINE',
                      trust_level INTEGER DEFAULT 0
                    );
                """
                )
                con.commit()
                con.close()

                # Mock AuthDB
                mock_auth_db = MagicMock()

                def get_db():
                    conn = sqlite3.connect(db_path)
                    conn.row_factory = sqlite3.Row
                    return conn

                mock_auth_db._db.side_effect = get_db

                manager = MeshNetworkManager(mock_auth_db)

                # 1. Test Identity
                pub, node_id = ensure_mesh_identity()
                print(f"Local Node ID: {node_id}")
                assert node_id.startswith("HUB-")

                # 2. Test Signing
                msg = b"hello mesh"
                sig = sign_message(msg)
                assert verify_signature(pub, msg, sig) is True
                print("Identity and Signing: OK")

                # 3. Test Handshake (Mocked)
                with patch("app.core.mesh_network.requests.post") as mock_post:

                    def _post(*args, **kwargs):
                        request_payload = kwargs.get("json") or {}
                        ok, _, peer = verify_handshake_envelope(
                            request_payload,
                            expected_purpose=HANDSHAKE_INIT_PURPOSE,
                        )
                        assert ok is True
                        challenge = str((peer or {}).get("challenge") or "")
                        assert challenge
                        response_payload = _build_external_ack(challenge)

                        mock_resp = MagicMock()
                        mock_resp.status_code = 200
                        mock_resp.json.return_value = response_payload
                        return mock_resp

                    mock_post.side_effect = _post

                    success = manager.initiate_handshake("1.2.3.4")
                    assert success is True

                peers = manager.get_peers()
                assert len(peers) == 1
                assert peers[0]["name"] == "External Hub"
                assert peers[0]["node_id"].startswith("HUB-")
                print("Handshake and Peer Registration: OK")

    print("Multi-Hub Sync Test: PASS")


if __name__ == "__main__":
    test_multi_hub_sync()


def test_mesh_handshake_endpoint_validates_envelope(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from app import create_app

    monkeypatch.setattr(Config, "USER_DATA_ROOT", tmp_path)
    monkeypatch.setattr(Config, "AUTH_DB", tmp_path / "auth.sqlite3")
    monkeypatch.setattr(Config, "CORE_DB", tmp_path / "core.sqlite3")
    monkeypatch.setattr(Config, "LICENSE_PATH", tmp_path / "license.json")
    monkeypatch.setattr(Config, "TRIAL_PATH", tmp_path / "trial.json")

    app = create_app()
    app.config["TESTING"] = True
    with app.app_context():
        auth_db = app.extensions["auth_db"]
        with auth_db._db() as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS mesh_nodes(
                    node_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    public_key TEXT NOT NULL,
                    last_ip TEXT,
                    last_seen TEXT,
                    status TEXT DEFAULT 'OFFLINE',
                    trust_level INTEGER DEFAULT 0
                )
                """
            )
            con.commit()
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user"] = "admin"
        sess["role"] = "ADMIN"
        sess["tenant_id"] = "KUKANILEA"

    good_envelope, ext_pub_b64 = _build_external_init(challenge="hello")
    ok_resp = client.post("/api/mesh/handshake", json=good_envelope)
    assert ok_resp.status_code == 200

    bad_envelope, _ = _build_external_init(challenge="hello", node_id="HUB-FAKEFAKEFAKEFAKE")
    bad_resp = client.post("/api/mesh/handshake", json=bad_envelope)
    assert bad_resp.status_code == 401
    assert bad_resp.get_json()["error"] == "node_key_mismatch"

    with app.app_context():
        auth_db = app.extensions["auth_db"]
        with auth_db._db() as con:
            row = con.execute(
                "SELECT node_id, public_key FROM mesh_nodes WHERE public_key = ?",
                (ext_pub_b64,),
            ).fetchone()
            assert row is not None
            assert row["node_id"] == compute_node_id(ext_pub_b64)
