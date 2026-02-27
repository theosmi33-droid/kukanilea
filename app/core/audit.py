"""
app/core/audit.py
Local Evidence Vault for GoBD compliance.
Implements WORM (Write Once Read Many) principles for document evidence.
"""

import json
import logging
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import Config

logger = logging.getLogger("kukanilea.audit")
_VAULT_LOCK = threading.Lock()


class AuditVault:
    def __init__(self, db_path: Optional[Path] = None):
        if db_path:
            self.path = Path(db_path)
        else:
            self.path = Config.USER_DATA_ROOT / "audit_vault.sqlite3"
        self._init_db()

    def _db(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path))
        conn.row_factory = sqlite3.Row
        # GoBD Performance & Safety
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        return conn

    def _init_db(self):
        with _VAULT_LOCK:
            con = self._db()
            try:
                con.execute("""
                    CREATE TABLE IF NOT EXISTS evidence_vault (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        doc_id TEXT NOT NULL,
                        tenant_id TEXT NOT NULL,
                        metadata_hash TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        signature TEXT
                    )
                """)
                con.execute("CREATE INDEX IF NOT EXISTS idx_vault_doc ON evidence_vault(doc_id)")
                con.execute("CREATE INDEX IF NOT EXISTS idx_vault_tenant ON evidence_vault(tenant_id)")
                con.commit()
            finally:
                con.close()

    def store_evidence(self, doc_id: str, tenant_id: str, metadata_hash: str, payload: Dict[str, Any]):
        """
        Stores evidence in the vault. 
        Strictly APPEND-ONLY at the application layer.
        """
        now = datetime.now(timezone.utc).isoformat()
        payload_str = json.dumps(payload, ensure_ascii=False)
        
        with _VAULT_LOCK:
            con = self._db()
            try:
                con.execute(
                    "INSERT INTO evidence_vault (doc_id, tenant_id, metadata_hash, payload_json, created_at) VALUES (?, ?, ?, ?, ?)",
                    (doc_id, tenant_id, metadata_hash, payload_str, now)
                )
                con.commit()
                logger.info(f"Evidence stored for doc {doc_id} in vault.")
            except Exception as e:
                logger.error(f"Failed to store evidence: {e}")
                raise
            finally:
                con.close()

    def get_audit_trail(self, tenant_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieves entries from the vault. NO UPDATE/DELETE provided."""
        con = self._db()
        try:
            if tenant_id:
                rows = con.execute(
                    "SELECT * FROM evidence_vault WHERE tenant_id=? ORDER BY created_at DESC LIMIT ?",
                    (tenant_id, limit)
                ).fetchall()
            else:
                rows = con.execute(
                    "SELECT * FROM evidence_vault ORDER BY created_at DESC LIMIT ?",
                    (limit,)
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            con.close()

    def verify_integrity(self) -> List[Dict[str, Any]]:
        """Placeholder for cryptographic chain verification if implemented later."""
        # For now, just return all entries for manual/script verification
        return self.get_audit_trail(limit=1000000)

# Global singleton for the app
vault = AuditVault()

def vault_store_evidence(doc_id: str, tenant_id: str, metadata_hash: str, payload: Dict[str, Any]):
    vault.store_evidence(doc_id, tenant_id, metadata_hash, payload)
