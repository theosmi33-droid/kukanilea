"""
app/seeder.py
Logik zur Injektion von Branchen-Vorlagen in die SQLite-Datenbank.
"""

import json
import logging
import uuid

from app.database import get_db_connection
from app.verticals import VERTICAL_KITS

logger = logging.getLogger("kukanilea.seeder")


def apply_vertical_kit(tenant_id: str, vertical: str):
    """
    Holt Vorlagen für das gewählte Gewerk und schreibt sie für den Tenant in die DB.
    """
    if vertical not in VERTICAL_KITS:
        logger.warning(f"Vertical kit '{vertical}' not found.")
        return False

    templates = VERTICAL_KITS[vertical]
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        for item in templates:
            entity_id = str(uuid.uuid4())
            cursor.execute(
                "INSERT INTO entities (id, tenant_id, type, data_json) VALUES (?, ?, ?, ?)",
                (entity_id, tenant_id, item["type"], json.dumps(item["data"])),
            )
        conn.commit()
        logger.info(
            f"Successfully applied vertical kit '{vertical}' for tenant '{tenant_id}'."
        )
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to apply vertical kit: {e}")
        return False
    finally:
        conn.close()
