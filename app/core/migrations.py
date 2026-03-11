"""
app/core/migrations.py
Database migration system. Supports background index building.
"""
import hashlib
import logging
import sqlite3
import threading
from pathlib import Path

logger = logging.getLogger("kukanilea.migrations")

# Current target schema version
CURRENT_SCHEMA_VERSION = 7


def _ensure_migration_targets(conn: sqlite3.Connection) -> None:
    """Ensure migration-owned tables/columns/indexes exist independent of user_version."""
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
    if not _column_exists(conn, "agent_memory", "importance_score"):
        conn.execute("ALTER TABLE agent_memory ADD COLUMN importance_score INTEGER DEFAULT 5;")
    if not _column_exists(conn, "agent_memory", "category"):
        conn.execute("ALTER TABLE agent_memory ADD COLUMN category TEXT DEFAULT 'FAKT';")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_tenant_ts ON agent_memory(tenant_id, timestamp);")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_memory_importance ON agent_memory(tenant_id, importance_score);"
    )

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

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS memory_audit_log(
          id TEXT PRIMARY KEY,
          memory_id TEXT NOT NULL,
          tenant_id TEXT NOT NULL,
          action TEXT NOT NULL,
          actor TEXT NOT NULL,
          payload TEXT,
          created_at TEXT NOT NULL
        );
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_memory_audit_tenant_ts ON memory_audit_log(tenant_id, created_at);"
    )

    if _table_exists(conn, "customers") and _column_exists(conn, "customers", "id"):
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_customers_id_unique ON customers(id);")

    _ensure_automation_execution_log_unique_index(conn)


def _ensure_automation_execution_log_unique_index(conn: sqlite3.Connection) -> None:
    """Normalize execution-log uniqueness to ignore empty trigger references."""
    table_name = "automation_builder_execution_log"
    if not _table_exists(conn, table_name):
        return
    if not _column_exists(conn, table_name, "trigger_ref"):
        conn.execute(
            "ALTER TABLE automation_builder_execution_log ADD COLUMN trigger_ref TEXT NOT NULL DEFAULT ''"
        )
    conn.execute("DROP INDEX IF EXISTS idx_automation_builder_execution_log_unique")
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_automation_builder_execution_log_unique "
        "ON automation_builder_execution_log(tenant_id, rule_id, trigger_ref) "
        "WHERE trigger_ref <> ''"
    )


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return bool(row)


def _column_exists(conn: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    if not _table_exists(conn, table_name):
        return False
    columns = [r[1] for r in conn.execute(f"PRAGMA table_info({table_name})").fetchall()]
    return column_name in columns


def _latest_version_text_column(conn: sqlite3.Connection) -> str | None:
    if not _table_exists(conn, "versions"):
        return None
    for candidate in ("extracted_text", "content", "text"):
        if _column_exists(conn, "versions", candidate):
            return candidate
    return None

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


def _ensure_docs_fts_schema(conn: sqlite3.Connection) -> None:
    expected_cols = {
        "doc_id",
        "tenant_id",
        "kdnr",
        "doctype",
        "doc_date",
        "file_name",
        "file_path",
        "content",
    }
    if _table_exists(conn, "docs_fts"):
        cols = {r[1] for r in conn.execute("PRAGMA table_info(docs_fts)").fetchall()}
        if not expected_cols.issubset(cols):
            conn.execute("DROP TABLE docs_fts")

    conn.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts
        USING fts5(
            doc_id UNINDEXED,
            tenant_id UNINDEXED,
            kdnr UNINDEXED,
            doctype UNINDEXED,
            doc_date UNINDEXED,
            file_name UNINDEXED,
            file_path UNINDEXED,
            content,
            tokenize='unicode61'
        )
        """
    )

def _build_fts_indices(db_path: str):
    """Worker to build FTS indices in background to avoid blocking boot."""
    logger.info("Starting background FTS index build...")
    conn = sqlite3.connect(db_path, timeout=5.0)
    try:
        conn.execute("PRAGMA busy_timeout=5000;")
        # 1. Create/repair FTS5 virtual table using runtime-compatible schema.
        _ensure_docs_fts_schema(conn)

        text_column = _latest_version_text_column(conn)
        if not text_column:
            logger.info("Skipping FTS sync: versions text column not available yet.")
            return

        # 2. Sync from docs + latest version metadata.
        # text_column is selected from a fixed internal allowlist in _latest_version_text_column.
        query = f"""  # nosec B608
            INSERT INTO docs_fts(doc_id, tenant_id, kdnr, doctype, doc_date, file_name, file_path, content)
            SELECT
                d.doc_id,
                COALESCE(d.tenant_id, ''),
                COALESCE(d.kdnr, ''),
                COALESCE(d.doctype, ''),
                COALESCE(d.doc_date, ''),
                COALESCE(v.file_name, ''),
                COALESCE(v.file_path, ''),
                COALESCE(v.{text_column}, '')
            FROM docs d
            LEFT JOIN versions v ON v.id = (
                SELECT vv.id FROM versions vv
                WHERE vv.doc_id = d.doc_id
                ORDER BY vv.version_no DESC, vv.id DESC
                LIMIT 1
            )
            WHERE d.doc_id NOT IN (SELECT doc_id FROM docs_fts)
            """
        conn.execute(query)
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
            if _latest_version_text_column(conn):
                t = threading.Thread(target=_build_fts_indices, args=(str(db_path),), daemon=True)
                t.start()
            else:
                logger.info("Skipping FTS thread: versions table/text column not ready.")
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
            if _table_exists(conn, "agent_memory"):
                if not _column_exists(conn, "agent_memory", "importance_score"):
                    conn.execute("ALTER TABLE agent_memory ADD COLUMN importance_score INTEGER DEFAULT 5;")
                if not _column_exists(conn, "agent_memory", "category"):
                    conn.execute("ALTER TABLE agent_memory ADD COLUMN category TEXT DEFAULT 'FAKT';")
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_memory_importance ON agent_memory(tenant_id, importance_score);"
                )
            _set_user_version(conn, 6)
            conn.commit()
            logger.info("Migrated to version 6 (Memory Intelligence)")


        if current_version < 7:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_audit_log(
                  id TEXT PRIMARY KEY,
                  memory_id TEXT NOT NULL,
                  tenant_id TEXT NOT NULL,
                  action TEXT NOT NULL,
                  actor TEXT NOT NULL,
                  payload TEXT,
                  created_at TEXT NOT NULL
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_memory_audit_tenant_ts ON memory_audit_log(tenant_id, created_at);"
            )
            _set_user_version(conn, 7)
            conn.commit()
            logger.info("Migrated to version 7 (Knowledge Memory audit trail)")

        # Always-on drift guard (idempotent)
        _ensure_migration_targets(conn)
        if _get_user_version(conn) < CURRENT_SCHEMA_VERSION:
            _set_user_version(conn, CURRENT_SCHEMA_VERSION)
        conn.commit()

    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        raise
    finally:
        conn.close()
