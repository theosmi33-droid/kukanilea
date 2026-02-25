"""
app/core/mesh_logic.py
Kern-Logik für den dezentralen Datenaustausch (Delta-Sync).
Verarbeitet den Abgleich der SQLite-Tabellen zwischen Hub und Clients.
"""

import sqlite3
import logging
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

logger = logging.getLogger("kukanilea.mesh")

def get_latest_changes(since_ts: str) -> Dict[str, List[Any]]:
    """Extrahiert alle Datensätze, die seit since_ts geändert wurden."""
    from app.config import Config
    con = sqlite3.connect(str(Config.CORE_DB))
    con.row_factory = sqlite3.Row
    
    changes = {
        "docs": [],
        "entities": [],
        "agent_drafts": []
    }
    
    try:
        # Hinweis: Wir gehen davon aus, dass Tabellen eine created_at/updated_at Spalte haben.
        # In der Gold-v1.5.0 nutzen wir created_at für Docs.
        changes["docs"] = [dict(r) for r in con.execute("SELECT * FROM docs WHERE created_at > ?", (since_ts,)).fetchall()]
        changes["agent_drafts"] = [dict(r) for r in con.execute("SELECT * FROM agent_drafts WHERE created_at > ?", (since_ts,)).fetchall()]
        
        logger.info(f"Mesh: {len(changes['docs'])} neue Dokumente für Sync bereit.")
        return changes
    except Exception as e:
        logger.error(f"Fehler beim Delta-Export: {e}")
        return changes
    finally:
        con.close()

def apply_remote_delta(delta: Dict[str, List[Dict[str, Any]]]):
    """Wendet empfangene Delta-Änderungen auf die lokale Datenbank an."""
    from app.config import Config
    con = sqlite3.connect(str(Config.CORE_DB))
    
    try:
        for doc in delta.get("docs", []):
            con.execute(
                "INSERT OR IGNORE INTO docs(doc_id, group_key, tenant_id, kdnr, doctype, doc_date, created_at) VALUES (?,?,?,?,?,?,?)",
                (doc["doc_id"], doc["group_key"], doc["tenant_id"], doc["kdnr"], doc["doctype"], doc["doc_date"], doc["created_at"])
            )
        con.commit()
        logger.info("Mesh: Delta-Sync erfolgreich angewendet.")
    except Exception as e:
        logger.error(f"Fehler beim Delta-Import: {e}")
    finally:
        con.close()
