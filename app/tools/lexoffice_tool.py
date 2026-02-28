from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from app.config import Config
from app.tools.base_tool import BaseTool
from app.tools.registry import registry
from flask import current_app, g

class LexofficeUploadTool(BaseTool):
    """
    Tool for queuing document uploads to Lexoffice.
    Implements Store & Forward for offline resilience.
    """

    name = "lexoffice_upload"
    description = "Legt ein Dokument in den Postausgang zur Übertragung an Lexoffice."
    input_schema = {
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "Der Pfad zur lokalen Datei."},
            "type": {"type": "string", "enum": ["voucher", "evidence"], "default": "voucher"}
        },
        "required": ["file_path"]
    }

    def run(self, file_path: str, type: str = "voucher") -> Any:
        api_key = Config.LEXOFFICE_API_KEY
        if not api_key:
            return {"error": "Lexoffice Integration ist nicht konfiguriert (API Key fehlt)."}

        path = Path(file_path)
        if not path.exists():
            return {"error": f"Datei nicht gefunden: {file_path}"}

        tenant_id = g.get("tenant_id", "default")
        auth_db = current_app.extensions.get("auth_db")
        if not auth_db:
            return {"error": "Datenbank nicht verfügbar."}

        # Queue the job instead of direct upload
        job_id = str(uuid.uuid4())
        payload = {"voucher_type": type}
        ts = datetime.now(timezone.utc).isoformat() + "Z"

        try:
            with auth_db._db() as con:
                con.execute(
                    """
                    INSERT INTO api_outbound_queue (id, tenant_id, target_system, payload, file_path, status, created_at)
                    VALUES (?, ?, ?, ?, ?, 'pending', ?)
                    """,
                    (job_id, tenant_id, "lexoffice", json.dumps(payload), str(path.absolute()), ts)
                )
                con.commit()
            
            return {
                "status": "queued",
                "job_id": job_id,
                "message": "Dokument wurde in den Postausgang gelegt und wird synchronisiert, sobald das Netzwerk stabil is."
            }
        except Exception as e:
            return {"error": f"Fehler beim Warteschlangen-Eintrag: {e}"}

# Register tool
registry.register(LexofficeUploadTool())
