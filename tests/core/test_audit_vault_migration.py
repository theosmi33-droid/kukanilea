import sqlite3
from pathlib import Path
from app.core.audit import AuditVault

def test_audit_vault_migrates_legacy_schema_and_stores_evidence(tmp_path: Path) -> None:
    db_path = tmp_path / "audit_legacy.sqlite3"
    con = sqlite3.connect(str(db_path))
    try:
        con.execute(
            """
            CREATE TABLE evidence_vault (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_id TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                metadata_hash TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                prev_hash TEXT NOT NULL,
                node_hash TEXT NOT NULL
            )
            """
        )
        con.commit()
    finally:
        con.close()

    vault = AuditVault(db_path=db_path)
    vault.store_evidence(
        doc_id="doc-1",
        tenant_id="TENANT_A",
        metadata_hash="mhash",
        payload={"scan_status": "CLEAN"},
    )
