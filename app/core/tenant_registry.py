from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional
from ..config import Config

class TenantRegistry:
    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or Config.USER_DATA_ROOT / "tenant_mapping.json"
        self._mappings: Dict[str, dict] = self._load()

    def _load(self) -> Dict[str, dict]:
        if not self.storage_path.exists():
            return {}
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save(self):
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(self._mappings, f, indent=2)

    def validate_path(self, db_path: str) -> bool:
        """
        Security Guard: Validates that the path is absolute, ends in .db or .sqlite,
        and is within allowed directories (no path traversal).
        """
        try:
            path = Path(db_path).resolve()
            
            # 1. Must be absolute
            if not path.is_absolute():
                return False
            
            # 2. Must end in .db or .sqlite
            if not (path.suffix.lower() in [".db", ".sqlite", ".sqlite3"]):
                return False
            
            # 3. Block system paths (e.g., /etc, /bin, /usr, /proc, /sys)
            blocked_prefixes = ["/etc", "/bin", "/usr", "/proc", "/sys", "/var", "/root", "/boot", "/dev"]
            if any(str(path).startswith(p) for p in blocked_prefixes):
                return False
            
            # 4. Allowlist: User Home and User Data Root
            allowed_roots = [
                Config.USER_DATA_ROOT.resolve(),
                Path.home().resolve()
            ]
            
            if any(str(path).startswith(str(root)) for root in allowed_roots):
                return True
            
            return False
        except Exception:
            return False

    def add_tenant(self, tenant_id: str, tenant_name: str, db_path: str) -> bool:
        if not self.validate_path(db_path):
            return False
        
        self._mappings[tenant_id] = {
            "name": tenant_name,
            "db_path": str(Path(db_path).resolve())
        }
        self._save()
        return True

    def get_tenant(self, tenant_id: str) -> Optional[dict]:
        return self._mappings.get(tenant_id)

    def list_tenants(self) -> List[dict]:
        return [
            {"id": tid, "name": m["name"], "db_path": m["db_path"]}
            for tid, m in self._mappings.items()
        ]

    def remove_tenant(self, tenant_id: str):
        if tenant_id in self._mappings:
            del self._mappings[tenant_id]
            self._save()

# Global Instance
tenant_registry = TenantRegistry()
