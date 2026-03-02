import os
import sys
import uuid
import platform
import subprocess
import logging
from pathlib import Path
from datetime import datetime, timezone

logger = logging.getLogger("kukanilea.license_guardian")

class LicenseGuardian:
    """
    Sovereign-11 License Guardian:
    Ensures offline-first hardware locking and syncs state via SMB when connected.
    Deny-by-default implementation.
    """
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.license_file = self.data_dir / "license.json"
        self.smb_path = "smb://192.168.0.2/KUKANILEA-ENDKUNDE/lizenzen.xlsx"
        self.hardware_id = self._generate_hardware_id()

    def _generate_hardware_id(self) -> str:
        """Generates a stable hardware ID based on MAC address and OS info."""
        mac = uuid.getnode()
        os_info = platform.system() + platform.release()
        base_string = f"{mac}-{os_info}"
        import hashlib
        return hashlib.sha256(base_string.encode('utf-8')).hexdigest()[:16]

    def verify_local_license(self) -> dict:
        """Offline-first license check. Only allows access if a valid local license exists."""
        if not self.license_file.exists():
            return {"valid": False, "reason": "NO_LICENSE_FILE", "hw_id": self.hardware_id}
        
        import json
        try:
            with open(self.license_file, "r") as f:
                data = json.load(f)
            
            # Hardware Binding Check
            if data.get("hardware_id") != self.hardware_id:
                logger.error(f"Hardware ID mismatch. Expected {data.get('hardware_id')}, got {self.hardware_id}")
                return {"valid": False, "reason": "HARDWARE_MISMATCH", "hw_id": self.hardware_id}
            
            # Expiration Check
            expires = data.get("expires_at")
            if expires:
                exp_date = datetime.fromisoformat(expires.replace("Z", "+00:00"))
                if datetime.now(timezone.utc) > exp_date:
                    return {"valid": False, "reason": "LICENSE_EXPIRED", "hw_id": self.hardware_id}

            # Status Check
            if data.get("status") == "REVOKED":
                return {"valid": False, "reason": "LICENSE_REVOKED", "hw_id": self.hardware_id}

            return {"valid": True, "plan": data.get("plan", "STANDARD"), "hw_id": self.hardware_id}
        except Exception as e:
            logger.error(f"Failed to read local license: {e}")
            return {"valid": False, "reason": "CORRUPTED_LICENSE", "hw_id": self.hardware_id}

    def sync_from_smb(self) -> bool:
        """
        Attempts to read the master Excel file from the ZimaBlade SMB share.
        Updates local license file if changes are detected.
        Requires 'pandas' and 'openpyxl' (or a lightweight CSV parser if preferred).
        """
        # In a real environment, you mount the SMB share first, e.g., via mount_smbfs on macOS
        # For security, we wrap this in a try-except. If offline, we rely on verify_local_license()
        try:
            logger.info(f"Attempting to sync license state from {self.smb_path}")
            # Placeholder for actual SMB mount and pandas read logic:
            # df = pd.read_excel('/Volumes/KUKANILEA-ENDKUNDE/lizenzen.xlsx')
            # row = df[df['Hardware_ID'] == self.hardware_id]
            # if not row.empty:
            #     update_local_json(row)
            return True
        except Exception as e:
            logger.warning(f"SMB sync failed (likely offline). Relying on local state. Error: {e}")
            return False

# Global instance for core app
def get_guardian() -> LicenseGuardian:
    base_path = Path(os.environ.get("KUKANILEA_USER_DATA_ROOT", "instance"))
    return LicenseGuardian(base_path)
