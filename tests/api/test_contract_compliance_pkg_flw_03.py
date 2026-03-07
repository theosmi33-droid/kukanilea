
import pytest
from app import create_app

@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    app.config['DEBUG'] = False
    with app.test_client() as client:
        with app.app_context():
            with client.session_transaction() as sess:
                sess['tenant_id'] = 'KUKANILEA'
            yield client

def test_api_contracts_exist(client):
    endpoints = [
        "/api/kalender/summary",
        "/api/kalender/health",
        "/api/aufgaben/summary",
        "/api/aufgaben/health",
        "/api/projekte/summary",
        "/api/projekte/health",
        "/api/zeiterfassung/summary",
        "/api/zeiterfassung/health",
    ]
    for ep in endpoints:
        response = client.get(ep)
        if response.status_code != 200:
            print(f"FAILED {ep}: {response.status_code}")
            print(response.get_data(as_text=True))
        assert response.status_code == 200
        data = response.get_json()
        assert "status" in data
        assert "timestamp" in data
        if "health" in ep:
            assert "metrics" in data
            assert "backend_ready" in data["metrics"]
