from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional

from ..config import Config

TENANT_ID_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9_-]{0,62}[a-z0-9])?$")


class TenantRegistry:
    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or Config.USER_DATA_ROOT / "tenant_mapping.json"
        self.tenants_root = Config.USER_DATA_ROOT / "tenants"
        self._ensure_dir(self.tenants_root)
        self._mappings: Dict[str, dict] = self._load()

    @staticmethod
    def normalize_tenant_id(raw_tenant_id: str) -> Optional[str]:
        cleaned = re.sub(r"[^a-z0-9_-]+", "_", str(raw_tenant_id or "").strip().lower())
        cleaned = cleaned.strip("_-")
        if not cleaned or not TENANT_ID_PATTERN.fullmatch(cleaned):
            return None
        return cleaned

    @staticmethod
    def _ensure_dir(path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(path, 0o700)
        except OSError:
            pass

    @staticmethod
    def _is_within(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False

    def _tenant_root(self, tenant_id: str) -> Path:
        normalized = self.normalize_tenant_id(tenant_id)
        if not normalized:
            raise ValueError("invalid_tenant_id")
        root = (self.tenants_root / normalized).resolve()
        if not self._is_within(root, self.tenants_root.resolve()):
            raise ValueError("tenant_root_escape")
        return root

    def _load(self) -> Dict[str, dict]:
        if not self.storage_path.exists():
            return {}
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if not isinstance(raw, dict):
                return {}

            cleaned: Dict[str, dict] = {}
            for tenant_id, meta in raw.items():
                normalized = self.normalize_tenant_id(str(tenant_id))
                if not normalized or not isinstance(meta, dict):
                    continue

                db_path = str(meta.get("db_path") or "")
                name = str(meta.get("name") or normalized)
                if not self.validate_path(db_path, normalized):
                    continue

                cleaned[normalized] = {
                    "name": name,
                    "db_path": str(Path(db_path).expanduser().resolve()),
                    "root_path": str(self._tenant_root(normalized)),
                }
            return cleaned
        except Exception:
            return {}

    def _save(self) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(self._mappings, f, indent=2)
        try:
            os.chmod(self.storage_path, 0o600)
        except OSError:
            pass

    def validate_path(self, db_path: str, tenant_id: Optional[str] = None) -> bool:
        """
        Security Guard: allows only absolute SQLite paths inside the dedicated tenant
        filesystem sandbox. Symlinks and tenant-escape paths are blocked.
        """
        try:
            candidate = Path(db_path).expanduser()
            if not candidate.is_absolute():
                return False

            if candidate.suffix.lower() not in {".db", ".sqlite", ".sqlite3"}:
                return False

            if candidate.exists() and candidate.is_symlink():
                return False
            if candidate.parent.exists() and candidate.parent.is_symlink():
                return False

            resolved = candidate.resolve(strict=False)
            if not self._is_within(resolved, self.tenants_root.resolve()):
                return False

            if tenant_id:
                tenant_root = self._tenant_root(tenant_id)
                return self._is_within(resolved, tenant_root)

            return True
        except Exception:
            return False

    def add_tenant(self, tenant_id: str, tenant_name: str, db_path: str) -> bool:
        normalized = self.normalize_tenant_id(tenant_id)
        if not normalized:
            return False

        if not self.validate_path(db_path, normalized):
            return False

        tenant_root = self._tenant_root(normalized)
        self._ensure_dir(tenant_root)

        resolved_db_path = Path(db_path).expanduser().resolve()
        self._ensure_dir(resolved_db_path.parent)

        self._mappings[normalized] = {
            "name": tenant_name,
            "db_path": str(resolved_db_path),
            "root_path": str(tenant_root),
        }
        self._save()
        return True

    def get_tenant(self, tenant_id: str) -> Optional[dict]:
        normalized = self.normalize_tenant_id(tenant_id)
        if not normalized:
            return None
        return self._mappings.get(normalized)

    def list_tenants(self) -> List[dict]:
        return [
            {
                "id": tid,
                "name": m["name"],
                "db_path": m["db_path"],
                "root_path": m.get("root_path", ""),
            }
            for tid, m in self._mappings.items()
        ]

    def remove_tenant(self, tenant_id: str):
        normalized = self.normalize_tenant_id(tenant_id)
        if normalized and normalized in self._mappings:
            del self._mappings[normalized]
            self._save()


# Global Instance
tenant_registry = TenantRegistry()
