from __future__ import annotations


def test_zeiterfassung_summary_contract(auth_client):
    response = auth_client.get("/api/zeiterfassung/summary")
    assert response.status_code == 200
    body = response.get_json()
    assert set(body.keys()) == {"status", "timestamp", "metrics"}
    assert body["status"] in {"ok", "degraded", "error"}
    assert isinstance(body["timestamp"], str)
    assert isinstance(body["metrics"], dict)


def test_zeiterfassung_health_contract(auth_client):
    response = auth_client.get("/api/zeiterfassung/health")
    assert response.status_code in {200, 503}
    body = response.get_json()
    assert set(body.keys()) == {"status", "timestamp", "metrics"}
    assert body["status"] in {"ok", "degraded", "error"}
    assert isinstance(body["timestamp"], str)
    assert isinstance(body["metrics"], dict)
    assert set(body["metrics"].keys()) >= {"backend_ready", "offline_safe"}
