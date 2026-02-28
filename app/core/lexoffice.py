from __future__ import annotations

import logging
import requests
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("kukanilea.lexoffice")

class LexofficeClient:
    """
    Client for the Lexoffice Public API.
    Handles authentication and document exchange.
    """
    
    BASE_URL = "https://api.lexoffice.de/v1"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json"
        }

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def upload_file(self, file_path: Path, voucher_type: str = "voucher") -> Optional[str]:
        """
        Uploads a document to Lexoffice.
        voucher_type can be 'voucher' or 'evidence'.
        Returns the file ID if successful.
        """
        if not self.is_configured():
            logger.error("Lexoffice API key missing.")
            return None

        url = f"{self.BASE_URL}/files"
        
        try:
            with open(file_path, "rb") as f:
                files = {
                    "file": (file_path.name, f, "application/pdf")
                }
                # Lexoffice requires 'type' as a form field
                data = {"type": voucher_type}
                
                response = requests.post(url, headers=self.headers, files=files, data=data, timeout=30)
                response.raise_for_status()
                
                res_data = response.json()
                return res_data.get("id")
        except Exception as e:
            logger.error(f"Lexoffice upload failed for {file_path.name}: {e}")
            return None

    def get_contacts(self) -> List[Dict[str, Any]]:
        """
        Retrieves a list of contacts from Lexoffice.
        Used for mapping KUKANILEA customers to Lexoffice contacts.
        """
        if not self.is_configured():
            return []

        url = f"{self.BASE_URL}/contacts"
        try:
            response = requests.get(url, headers=self.headers, timeout=20)
            response.raise_for_status()
            return response.json().get("content", [])
        except Exception as e:
            logger.error(f"Failed to fetch Lexoffice contacts: {e}")
            return []
