"""
tests/test_seeding.py
Evidence Test für das Vertical Kit Seeding (EPIC 6).
"""

import uuid

from app.database import DB_PATH, get_db_connection, init_db
from app.seeder import apply_vertical_kit


def test_apply_vertical_kit_seeding():
    """
    Verifiziert, dass apply_vertical_kit Datensätze in die 'entities' Tabelle schreibt.
    """
    # Ensure fresh DB state
    if DB_PATH.exists():
        DB_PATH.unlink()
    init_db()

    tenant = "test_tenant_seeding"
    vertical = "dach"

    # Run seeder
    success = apply_vertical_kit(tenant, vertical)
    assert success is True

    # Verify DB state
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM entities WHERE tenant_id = ?", (tenant,))
        count = cursor.fetchone()[0]

        # 'dach' has 5 items in the updated VERTICAL_KITS
        assert count == 5

        cursor.execute(
            "SELECT id, type, data_json FROM entities WHERE tenant_id = ?", (tenant,)
        )
        rows = cursor.fetchall()
        types = [row["type"] for row in rows]
        assert "task" in types
        assert "workflow" in types
        assert "tag" in types
        
        # Verify IDs are valid UUIDs
        for row in rows:
            assert uuid.UUID(row["id"])
            
    finally:
        conn.close()
