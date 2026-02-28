"""
app/core/audit.py
Forensic Evidence Vault for GoBD compliance.
Implements a cryptographic hash chain (Immutable Chain) for document evidence.
"""

import hashlib
import json
import logging
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.config import Config

logger = logging.getLogger("kukanilea.audit")
_VAULT_LOCK = threading.Lock()

GENESIS_HASH = "KUKANILEA_GENESIS_v2.0_2026"

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
                # Task 1: Chained Schema
                con.execute("""
                    CREATE TABLE IF NOT EXISTS evidence_vault (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        doc_id TEXT NOT NULL,
                        tenant_id TEXT NOT NULL,
                        metadata_hash TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        prev_hash TEXT NOT NULL,
                        node_hash TEXT NOT NULL,
                        signature TEXT
                    )
                """)
                con.execute("CREATE INDEX IF NOT EXISTS idx_vault_doc ON evidence_vault(doc_id)")
                con.execute("CREATE INDEX IF NOT EXISTS idx_vault_tenant ON evidence_vault(tenant_id)")
                
                # Task 2: Immutability Triggers
                con.execute("""
                    CREATE TRIGGER IF NOT EXISTS prevent_vault_deletion
                    BEFORE DELETE ON evidence_vault
                    BEGIN
                        SELECT RAISE(FAIL, 'Forensic vault entries are immutable and cannot be deleted.');
                    END;
                """)
                con.execute("""
                    CREATE TRIGGER IF NOT EXISTS prevent_vault_update
                    BEFORE UPDATE ON evidence_vault
                    BEGIN
                        SELECT RAISE(FAIL, 'Forensic vault entries are immutable and cannot be modified.');
                    END;
                """)
                con.commit()
            finally:
                con.close()

    def _calculate_hash(self, data: str) -> str:
        return hashlib.sha256(data.encode("utf-8")).hexdigest()

    def _get_last_hash(self, cursor: sqlite3.Cursor) -> str:
        row = cursor.execute("SELECT node_hash FROM evidence_vault ORDER BY id DESC LIMIT 1").fetchone()
        return row["node_hash"] if row else GENESIS_HASH

    def store_evidence(self, doc_id: str, tenant_id: str, metadata_hash: str, payload: Dict[str, Any]):
        """
        Stores evidence in the vault with cryptographic chaining.
        """
        now = datetime.now(timezone.utc).isoformat()
        payload_str = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        
        with _VAULT_LOCK:
            con = self._db()
            try:
                # 1. Get previous hash
                prev_hash = self._get_last_hash(con)
                
                # 2. Calculate node hash
                # Data vector for hash: ts + doc + tenant + meta + payload + prev
                data_vector = f"{now}|{doc_id}|{tenant_id}|{metadata_hash}|{payload_str}|{prev_hash}"
                node_hash = self._calculate_hash(data_vector)
                
                # 3. Insert
                con.execute(
                    """
                    INSERT INTO evidence_vault (
                        doc_id, tenant_id, metadata_hash, payload_json, created_at, prev_hash, node_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (doc_id, tenant_id, metadata_hash, payload_str, now, prev_hash, node_hash)
                )
                con.commit()
                logger.info(f"Evidence stored for doc {doc_id} in forensic vault. Hash: {node_hash[:8]}")
            except Exception as e:
                logger.error(f"Failed to store forensic evidence: {e}")
                raise
            finally:
                con.close()

    def get_audit_trail(self, tenant_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        con = self._db()
        try:
            if tenant_id:
                rows = con.execute(
                    "SELECT * FROM evidence_vault WHERE tenant_id=? ORDER BY id DESC LIMIT ?",
                    (tenant_id, limit)
                ).fetchall()
            else:
                rows = con.execute(
                    "SELECT * FROM evidence_vault ORDER BY id DESC LIMIT ?",
                    (limit,)
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            con.close()

    def verify_chain(self) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Walks the entire chain and verifies cryptographic integrity.
        Returns (success, errors).
        """
        con = self._db()
        errors = []
        try:
            rows = con.execute("SELECT * FROM evidence_vault ORDER BY id ASC").fetchall()
            expected_prev = GENESIS_HASH
            
            for row in rows:
                # Re-calculate hash
                data_vector = f"{row['created_at']}|{row['doc_id']}|{row['tenant_id']}|{row['metadata_hash']}|{row['payload_json']}|{row['prev_hash']}"
                calculated = self._calculate_hash(data_vector)
                
                # Check 1: Prev hash match
                if row["prev_hash"] != expected_prev:
                    errors.append({"id": row["id"], "error": "Prev-Hash Mismatch (Chain broken)"})
                
                # Check 2: Node hash match
                if row["node_hash"] != calculated:
                    errors.append({"id": row["id"], "error": "Node-Hash Mismatch (Data tampered)"})
                
                expected_prev = row["node_hash"]
                
            return (len(errors) == 0, errors)
        finally:
            con.close()

# Global singleton
vault = AuditVault()

def vault_store_evidence(doc_id: str, tenant_id: str, metadata_hash: str, payload: Dict[str, Any]):
    vault.store_evidence(doc_id, tenant_id, metadata_hash, payload)
