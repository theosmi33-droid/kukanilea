
import pytest
from app import create_app

@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    app.config['DEBUG'] = False
    app.config['READ_ONLY'] = False # Disable read-only to test confirm gate specifically
    with app.test_client() as client:
        with app.app_context():
            # Mock session values
            with client.session_transaction() as sess:
                sess['tenant_id'] = 'KUKANILEA'
                sess['user'] = 'test-user'
                sess['role'] = 'ADMIN' # Admin role to bypass some checks if needed
            yield client

def test_kalender_create_event_requires_confirm_gate(client):
    # This route is now protected by the global _enforce_confirm_gates handler
    payload = {
        "title": "Exploit Event",
        "starts_at": "2026-03-06T10:00:00Z"
    }
    # We simulate a request without a 'confirm' token
    response = client.post("/api/kalender/events", json=payload)
    
    # Target behavior for PKG-GRD-02: It should fail (409 Conflict / Confirm Required)
    assert response.status_code == 409
    data = response.get_json()
    assert data["ok"] is False
    assert data["error"]["code"] == "confirm_required"

def test_kalender_create_event_with_valid_confirm_gate(client):
    # This route is now protected by the global _enforce_confirm_gates handler
    payload = {
        "title": "Legitimate Event",
        "starts_at": "2026-03-06T10:00:00Z",
        "confirm": "CONFIRM"
    }
    # We simulate a request with a valid 'confirm' token
    response = client.post("/api/kalender/events", json=payload)
    
    # Behavior with valid confirm: It should succeed (201 Created)
    assert response.status_code == 201
    assert response.get_json()["ok"] is True
