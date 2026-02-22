import pytest
import json
from fastapi.testclient import TestClient
from kukanilea_app import app
from app.database import get_db_connection, init_db

client = TestClient(app)

def test_onboarding_seeding():
    """Verify that vertical kit selection seeds the database correctly."""
    init_db()
    
    # Select SHK kit
    response = client.post("/ui/onboarding/setup", data={"vertical": "shk"})
    assert response.status_code == 204
    assert response.headers["HX-Redirect"] == "/crm/"
    
    # Check DB content
    conn = get_db_connection()
    rows = conn.execute("SELECT name FROM templates WHERE vertical = 'shk'").fetchall()
    names = [row["name"] for row in rows]
    
    assert "Protokoll: Wartung Gastherme" in names
    assert "Materialliste: Badsanierung" in names
    conn.close()
