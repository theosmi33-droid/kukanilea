from __future__ import annotations


def test_zeiterfassung_summary_contract(auth_client):
    response = auth_client.get("/api/zeiterfassung/summary")
    assert response.status_code == 200
    body = response.get_json()
    assert set(body.keys()) >= {"tool", "status", "updated_at", "metrics", "details"}
    assert body["tool"] == "zeiterfassung"
    assert body["status"] in {"ok", "degraded", "error"}
    assert isinstance(body["updated_at"], str)
    assert isinstance(body["metrics"], dict)


def test_zeiterfassung_health_contract(auth_client):
    response = auth_client.get("/api/zeiterfassung/health")
    assert response.status_code in {200, 503}
    body = response.get_json()
    assert set(body.keys()) >= {"tool", "status", "updated_at", "metrics", "details"}
    assert body["tool"] == "zeiterfassung"
    checks = body["details"].get("checks") or {}
    assert set(checks.keys()) == {"summary_contract", "backend_ready", "offline_safe"}
    assert isinstance(body["details"].get("offline_persistence"), bool)
