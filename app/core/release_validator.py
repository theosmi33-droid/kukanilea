from __future__ import annotations

import base64
import hashlib
import json
import logging
from pathlib import Path

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
except ImportError:
    Ed25519PublicKey = None  # type: ignore

logger = logging.getLogger("kukanilea.release")

# Dedicated public key for update verification (Example key)
# Matches the one used by KUKANILEA Release CI
UPDATE_PUBLIC_KEY_HEX = "d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5"  # pragma: allowlist secret


class ReleaseValidator:
    def __init__(self, public_key_hex: str = UPDATE_PUBLIC_KEY_HEX):
        self.public_key_hex = public_key_hex

    def verify_manifest(self, manifest_path: Path) -> bool:
        """
        Verifies the cryptographic signature of a release manifest.
        The manifest is a JSON file containing file hashes and a signature.
        """
        if not manifest_path.exists():
            logger.error(f"Manifest not found: {manifest_path}")
            return False

        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                raw = json.load(f)

            if not isinstance(raw, dict):
                return False

            signature_b64 = raw.get("signature")
            if not signature_b64:
                logger.error("Manifest is missing signature")
                return False

            payload = dict(raw)
            payload.pop("signature", None)

            # Canonicalize payload for verification
            payload_bytes = json.dumps(
                payload, separators=(",", ":"), sort_keys=True
            ).encode("utf-8")

            if Ed25519PublicKey is None:
                logger.error("Cryptography library missing")
                return False

            public_key = Ed25519PublicKey.from_public_bytes(
                bytes.fromhex(self.public_key_hex)
            )
            signature = base64.b64decode(signature_b64)

            public_key.verify(signature, payload_bytes)
            logger.info(
                f"Manifest signature VERIFIED for version {payload.get('version')}"
            )
            return True

        except Exception as e:
            logger.error(f"Manifest verification FAILED: {e}")
            return False

    def verify_files(self, manifest_path: Path, root_dir: Path) -> bool:
        """
        Checks if the hashes of local files match the signed manifest.
        """
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)

            files = manifest.get("files", {})
            for rel_path, expected_hash in files.items():
                abs_path = root_dir / rel_path
                if not abs_path.exists():
                    logger.error(f"Missing file: {rel_path}")
                    return False

                actual_hash = self._sha256_file(abs_path)
                if actual_hash != expected_hash:
                    logger.error(
                        f"Hash mismatch for {rel_path}! Expected: {expected_hash}, Actual: {actual_hash}"
                    )
                    return False

            logger.info("All files verified against manifest hashes.")
            return True
        except Exception as e:
            logger.error(f"File verification failed: {e}")
            return False

    def _sha256_file(self, fp: Path) -> str:
        h = hashlib.sha256()
        with open(fp, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
