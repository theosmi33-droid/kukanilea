from __future__ import annotations


def test_kalender_summary_contract(auth_client):
    response = auth_client.get("/api/kalender/summary")
    assert response.status_code == 200
    body = response.get_json()
    assert set(body.keys()) >= {"tool", "status", "updated_at", "metrics", "details"}
    assert body["tool"] == "kalender"
    assert body["status"] in {"ok", "degraded", "error"}
    assert isinstance(body["updated_at"], str)
    details = body["details"]
    assert isinstance(details.get("events_next_7_days"), list)
    assert isinstance(details.get("conflicts"), list)
    assert isinstance(details.get("reminders_due"), list)
    assert details.get("window_days") == 7
    assert isinstance(body["metrics"], dict)


def test_kalender_health_contract(auth_client):
    response = auth_client.get("/api/kalender/health")
    assert response.status_code in {200, 503}
    body = response.get_json()
    assert set(body.keys()) >= {"tool", "status", "updated_at", "metrics", "details"}
    assert body["tool"] == "kalender"
    checks = body["details"].get("checks") or {}
    assert set(checks.keys()) == {"summary_contract", "backend_ready", "offline_safe"}
    assert isinstance(body["details"].get("offline_persistence"), bool)
