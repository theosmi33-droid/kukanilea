"""
app/core/migrations.py
Database migration system. Supports background index building.
"""
import sqlite3
import logging
import threading
import hashlib
from pathlib import Path

logger = logging.getLogger("kukanilea.migrations")

# Current target schema version
CURRENT_SCHEMA_VERSION = 6

def _customer_stable_id(tenant_id: str, kdnr: str) -> str:
    raw = f"{tenant_id.strip()}|{kdnr.strip()}".encode("utf-8")
    return "cust_" + hashlib.sha256(raw).hexdigest()[:24]


def repair_legacy_customer_fk(db_path: Path) -> bool:
    """
    Repairs legacy core DBs where deals/leads reference customers(id)
    but customers table still uses (tenant_id, kdnr) without id.
    Idempotent by design.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    changed = False
    try:
        conn.execute("PRAGMA foreign_keys=OFF;")

        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='customers'"
        ).fetchone()
        if not exists:
            conn.execute("PRAGMA foreign_keys=ON;")
            return False

        cols = [r[1] for r in conn.execute("PRAGMA table_info(customers)").fetchall()]
        if "id" not in cols:
            conn.execute("ALTER TABLE customers ADD COLUMN id TEXT")
            changed = True

        rows = conn.execute(
            "SELECT rowid, tenant_id, kdnr, COALESCE(id, '') AS id FROM customers"
        ).fetchall()
        for row in rows:
            cid = str(row["id"] or "").strip()
            if cid:
                continue
            stable = _customer_stable_id(str(row["tenant_id"] or ""), str(row["kdnr"] or ""))
            # Collision-safe fallback (extremely unlikely)
            probe = stable
            n = 1
            while conn.execute(
                "SELECT 1 FROM customers WHERE id=? AND rowid<>?",
                (probe, row["rowid"]),
            ).fetchone():
                n += 1
                probe = f"{stable}_{n}"
            conn.execute("UPDATE customers SET id=? WHERE rowid=?", (probe, row["rowid"]))
            changed = True

        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_customers_id_unique ON customers(id)")

        conn.commit()
        conn.execute("PRAGMA foreign_keys=ON;")
        # Raises on schema mismatch in broken legacy setups if still unresolved
        conn.execute("PRAGMA foreign_key_check;").fetchall()
        return changed
    finally:
        conn.close()


def _get_user_version(conn: sqlite3.Connection) -> int:
    return conn.execute("PRAGMA user_version").fetchone()[0]

def _set_user_version(conn: sqlite3.Connection, version: int):
    conn.execute(f"PRAGMA user_version = {version}")

def _build_fts_indices(db_path: str):
    """Worker to build FTS indices in background to avoid blocking boot."""
    logger.info("Starting background FTS index build...")
    conn = sqlite3.connect(db_path)
    try:
        # 1. Create FTS5 virtual table if missing
        conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts USING fts5(doc_id, content)")
        
        # 2. Sync from main docs table
        conn.execute("""
            INSERT INTO docs_fts(doc_id, content)
            SELECT doc_id, extracted_text FROM docs
            WHERE doc_id NOT IN (SELECT doc_id FROM docs_fts)
        """)
        conn.commit()
        logger.info("✅ Background FTS index build complete.")
    except Exception as e:
        logger.error(f"FTS background build failed: {e}")
    finally:
        conn.close()

def run_migrations(db_path: Path):
    """Run sequential migrations up to CURRENT_SCHEMA_VERSION."""
    logger.info(f"Checking migrations for {db_path}")
    conn = sqlite3.connect(str(db_path))
    try:
        current_version = _get_user_version(conn)
        logger.info(f"Current DB version: {current_version}")
        
        if current_version < 1:
            _set_user_version(conn, 1)
            conn.commit()
            
        if current_version < 2:
            t = threading.Thread(target=_build_fts_indices, args=(str(db_path),), daemon=True)
            t.start()
            _set_user_version(conn, 2)
            conn.commit()

        if current_version < 3:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_memory(
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  tenant_id TEXT NOT NULL,
                  timestamp TEXT NOT NULL,
                  agent_role TEXT NOT NULL,
                  content TEXT NOT NULL,
                  embedding BLOB NOT NULL,
                  metadata TEXT,
                  FOREIGN KEY(tenant_id) REFERENCES tenants(tenant_id) ON DELETE CASCADE
                );
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_tenant_ts ON agent_memory(tenant_id, timestamp);")
            _set_user_version(conn, 3)
            conn.commit()

        if current_version < 4:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS mesh_nodes(
                  node_id TEXT PRIMARY KEY,
                  name TEXT NOT NULL,
                  public_key TEXT NOT NULL,
                  last_ip TEXT,
                  last_seen TEXT,
                  status TEXT DEFAULT 'OFFLINE',
                  trust_level INTEGER DEFAULT 0
                );
                """
            )
            _set_user_version(conn, 4)
            conn.commit()

        if current_version < 5:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS api_outbound_queue(
                  id TEXT PRIMARY KEY,
                  tenant_id TEXT NOT NULL,
                  target_system TEXT NOT NULL,
                  payload TEXT NOT NULL,
                  file_path TEXT,
                  status TEXT DEFAULT 'pending',
                  retry_count INTEGER DEFAULT 0,
                  created_at TEXT NOT NULL,
                  last_attempt TEXT,
                  error_message TEXT
                );
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_api_queue_status ON api_outbound_queue(status);")
            _set_user_version(conn, 5)
            conn.commit()

        if current_version < 6:
            # Task: Memory Intelligence (Importance & Category)
            conn.execute("ALTER TABLE agent_memory ADD COLUMN importance_score INTEGER DEFAULT 5;")
            conn.execute("ALTER TABLE agent_memory ADD COLUMN category TEXT DEFAULT 'FAKT';")
            _set_user_version(conn, 6)
            conn.commit()
            logger.info("Migrated to version 6 (Memory Intelligence)")
            
    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        raise
    finally:
        conn.close()
