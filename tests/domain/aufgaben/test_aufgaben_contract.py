from __future__ import annotations


def test_aufgaben_summary_contract(auth_client):
    response = auth_client.get("/api/aufgaben/summary")
    assert response.status_code == 200
    body = response.get_json()
    assert set(body.keys()) >= {"tool", "status", "updated_at", "metrics", "details"}
    assert body["tool"] == "aufgaben"
    assert body["status"] in {"ok", "degraded", "error"}
    assert set(body.get("metrics", {}).keys()) >= {"tasks_open", "tasks_overdue", "tasks_today"}
    assert body["details"].get("tenant") == "KUKANILEA"


def test_aufgaben_health_contract(auth_client):
    response = auth_client.get("/api/aufgaben/health")
    assert response.status_code in {200, 503}
    body = response.get_json()
    assert set(body.keys()) >= {"tool", "status", "updated_at", "metrics", "details"}
    assert body["tool"] == "aufgaben"
    checks = body["details"].get("checks") or {}
    assert set(checks.keys()) == {"summary_contract", "backend_ready", "offline_safe"}
