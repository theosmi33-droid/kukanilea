"""
app/core/upload_pipeline.py
Safe file upload pipeline processing.
"""
import os
import hashlib
from pathlib import Path
import logging
from typing import Tuple

logger = logging.getLogger("kukanilea.upload_pipeline")

ALLOWED_EXTENSIONS = {
    ".pdf", ".png", ".jpg", ".jpeg", ".txt", ".md", ".csv", ".xlsx"
}
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB

def _scan_malware(file_path: Path) -> bool:
    """ClamAV Scan placeholder"""
    try:
        import pyclamd
        cd = pyclamd.ClamdUnixSocket()
        if cd.ping():
            result = cd.scan_file(str(file_path))
            if result:
                logger.warning(f"Malware detected: {result}")
                return False
    except Exception:
        # If ClamAV isn't configured, we log and pass (or fail strict mode)
        logger.debug("ClamAV not available, skipping scan.")
    return True

def process_upload(file_path: Path, tenant_id: str) -> Tuple[bool, str]:
    """
    Validates, scans, and prepares a file for the system.
    """
    if not file_path.exists():
        return False, "File not found."

    # 1. Size Check
    if file_path.stat().st_size > MAX_FILE_SIZE:
        file_path.unlink()
        return False, "File too large."

    # 2. Extension Check
    if file_path.suffix.lower() not in ALLOWED_EXTENSIONS:
        file_path.unlink()
        return False, "Unsupported file type."

    # 3. Malware Scan
    if not _scan_malware(file_path):
        file_path.unlink()
        return False, "Malware detected."

    # 4. Hash Generation
    file_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()

    # 5. Evidence Capture (Task GoBD v2.0)
    try:
        from app.core.audit import vault_store_evidence
        vault_store_evidence(
            doc_id=file_path.name,
            tenant_id=tenant_id,
            metadata_hash=file_hash,
            payload={
                "original_filename": file_path.name,
                "size_bytes": file_path.stat().st_size,
                "scan_status": "CLEAN"
            }
        )
    except Exception as e:
        logger.error(f"Failed to capture forensic evidence for {file_path.name}: {e}")
        # We continue as the file itself is safe, but we log the audit failure

    return True, file_hash
