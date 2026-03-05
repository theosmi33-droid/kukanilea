from __future__ import annotations


def test_kalender_summary_endpoint_exists(auth_client):
    response = auth_client.get("/api/kalender/summary")
    assert response.status_code == 200
    body = response.get_json()
    assert "status" in body
    assert "metrics" in body


def test_kalender_health_endpoint_exists(auth_client):
    response = auth_client.get("/api/kalender/health")
    assert response.status_code in {200, 503}
    body = response.get_json()
    assert "status" in body
    assert "metrics" in body
