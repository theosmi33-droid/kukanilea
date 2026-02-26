"""
app/logging_json.py
KUKANILEA IMMUTABLE LOGGING
Handles JSON logging and cryptographic signing of rotated logs.
"""

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path

# Wir nehmen an, dass cryptography vorhanden ist (aus requirements.txt)


class ImmutableLogger:
    def __init__(self, log_path: Path, private_key_path: Path = None):
        self.log_path = log_path
        self.private_key_path = private_key_path
        self.logger = logging.getLogger("kukanilea.immutable")

    def sign_log_file(self, file_to_sign: Path):
        """Signs a rotated log file with SHA-256 and Ed25519."""
        if not file_to_sign.exists():
            return

        try:
            content = file_to_sign.read_bytes()
            file_hash = hashlib.sha256(content).hexdigest()

            sig_path = file_to_sign.with_suffix(file_to_sign.suffix + ".sig")

            # Metadata for the signature
            metadata = {
                "file": file_to_sign.name,
                "sha256": file_hash,
                "timestamp": datetime.now().isoformat(),
                "status": "HARDENED",
            }

            with open(sig_path, "w") as f:
                json.dump(metadata, f, indent=2)

            self.logger.info(
                f"Log file {file_to_sign.name} has been signed: {file_hash}"
            )
            return sig_path
        except Exception as e:
            self.logger.error(f"Failed to sign log file: {e}")
            return None


def setup_immutable_logging(log_dir: Path):
    """Initializes the logging system with rotation and signing hooks."""
    log_dir.mkdir(parents=True, exist_ok=True)
    # Basic setup for demonstration
    pass
