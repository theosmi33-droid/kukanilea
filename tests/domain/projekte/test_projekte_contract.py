from __future__ import annotations

from app.modules.projekte import contracts


def test_projekte_summary_contract(auth_client):
    response = auth_client.get("/api/projekte/summary")
    assert response.status_code == 200
    body = response.get_json()
    assert set(body.keys()) >= {"tool", "status", "updated_at", "metrics", "details"}
    assert body["tool"] == "projekte"
    assert body["status"] in {"ok", "degraded", "error"}
    assert isinstance(body["updated_at"], str)
    assert isinstance(body["metrics"], dict)


def test_projekte_health_contract(auth_client):
    response = auth_client.get("/api/projekte/health")
    assert response.status_code in {200, 503}
    body = response.get_json()
    assert set(body.keys()) >= {"tool", "status", "updated_at", "metrics", "details"}
    assert body["tool"] == "projekte"
    checks = body["details"].get("checks") or {}
    assert set(checks.keys()) == {"summary_contract", "backend_ready", "offline_safe"}


def test_projekte_build_health_uses_contract_response_helper():
    payload, status = contracts.build_health("KUKANILEA")
    assert status in {200, 503}
    assert payload["tool"] == "projekte"
