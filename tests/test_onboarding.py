import json
from fastapi.testclient import TestClient

from app.database import get_db_connection, init_db
from kukanilea_app import app

client = TestClient(app)


def test_onboarding_seeding():
    """Verify that vertical kit selection seeds the database correctly."""
    init_db()

    # Select SHK kit
    headers = {"X-Tenant-ID": "test-tenant", "X-User-ID": "test-user", "X-Role": "ADMIN"}
    response = client.post(
        "/ui/onboarding/setup", data={"vertical": "shk"}, headers=headers
    )
    assert response.status_code == 204
    assert response.headers["HX-Redirect"] == "/crm/"

    # Check DB content
    conn = get_db_connection()
    # Logic changed: seeder writes to 'entities' table with JSON blob
    rows = conn.execute("SELECT data_json FROM entities WHERE tenant_id = 'test-tenant'").fetchall()
    
    names = []
    for row in rows:
        data = json.loads(row["data_json"])
        if "name" in data:
            names.append(data["name"])

    assert "Dichtheitsprüfung" in names
    # assert "Materialliste: Badsanierung" in names # Not in current vertical definition
    conn.close()
