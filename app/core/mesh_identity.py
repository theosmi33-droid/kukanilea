from __future__ import annotations

import base64
import logging
import os
from pathlib import Path
from typing import Optional, Tuple

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from app.config import Config

logger = logging.getLogger("kukanilea.mesh_identity")

def get_identity_paths() -> Tuple[Path, Path]:
    root = Config.USER_DATA_ROOT
    priv_path = root / "mesh_id.priv"
    pub_path = root / "mesh_id.pub"
    return priv_path, pub_path

def ensure_mesh_identity() -> Tuple[str, str]:
    """
    Ensures that the Hub has a unique Ed25519 identity.
    Returns (public_key_b64, node_id).
    """
    priv_path, pub_path = get_identity_paths()
    
    if priv_path.exists() and pub_path.exists():
        try:
            pub_key_b64 = pub_path.read_text().strip()
            # node_id is a short hash of the public key
            node_id = pub_key_b64[:16] 
            return pub_key_b64, f"HUB-{node_id}"
        except Exception as e:
            logger.error(f"Failed to load mesh identity: {e}")

    logger.info("Generating new Mesh Identity keypair...")
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    # Save private key (unencrypted for now, as it's a local appliance)
    priv_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.OpenSSH,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    # Save public key
    pub_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    pub_b64 = base64.b64encode(pub_bytes).decode('utf-8')

    priv_path.parent.mkdir(parents=True, exist_ok=True)
    priv_path.write_bytes(priv_bytes)
    pub_path.write_text(pub_b64)
    
    # Set restrictive permissions on private key
    os.chmod(priv_path, 0o600)

    node_id = pub_b64[:16]
    return pub_b64, f"HUB-{node_id}"

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
    return base64.b64encode(sig).decode('utf-8')

def verify_signature(public_key_b64: str, message: bytes, signature_b64: str) -> bool:
    """Verifies a signature from a peer Hub."""
    try:
        pub_bytes = base64.b64decode(public_key_b64)
        sig_bytes = base64.b64decode(signature_b64)
        
        public_key = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)
        public_key.verify(sig_bytes, message)
        return True
    except Exception as e:
        logger.error(f"Signature verification failed: {e}")
        return False
