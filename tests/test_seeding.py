"""
tests/test_seeding.py
Evidence Test für das Vertical Kit Seeding (EPIC 6).
"""
import pytest
from app.database import init_db, get_db_connection, DB_PATH
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
        
        # 'dach' has 3 items in VERTICAL_KITS
        assert count == 3
        
        cursor.execute("SELECT type, data_json FROM entities WHERE tenant_id = ?", (tenant,))
        rows = cursor.fetchall()
        types = [row["type"] for row in rows]
        assert "task" in types
        assert "workflow" in types
    finally:
        conn.close()
