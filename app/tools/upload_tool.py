from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

from app.tools.base_tool import BaseTool
from app.core.upload_pipeline import process_upload, UploadResult
from app.modules.upload.document_processing import register_document_upload

logger = logging.getLogger("kukanilea.tools.upload")

class UploadTool(BaseTool):
    """
    Standardized tool for document ingestion and processing within KUKANILEA.
    """

    def __init__(self):
        super().__init__(
            name="upload_tool",
            description="Processes uploaded documents, performs malware scans, and registers them in the system.",
        )

    def execute(self, tenant_id: str, file_path: str, **kwargs) -> Dict[str, Any]:
        path = Path(file_path)
        if not path.exists():
            return {"success": False, "error": "file_not_found", "path": file_path}

        # 1. Pipeline Processing (Scan, Hash, Validate)
        result: UploadResult = process_upload(path, tenant_id)
        if not result.success:
            return {
                "success": False,
                "error": result.error_code.value if result.error_code else "unknown_error",
                "message": result.error_message,
            }

        # 2. Domain Registration
        try:
            reg = register_document_upload(
                file_path=path,
                tenant_id=tenant_id,
                file_hash=str(result.file_hash or ""),
            )
            return {
                "success": True,
                "upload_id": reg.get("upload_id"),
                "file_hash": result.file_hash,
                "metadata": reg.get("metadata"),
                "status": "registered",
            }
        except Exception as exc:
            logger.error("Failed to register upload %s: %s", path.name, exc)
            return {"success": False, "error": "registration_failed", "message": str(exc)}
