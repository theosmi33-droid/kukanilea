from __future__ import annotations


def test_einstellungen_summary_contract(auth_client):
    response = auth_client.get("/api/einstellungen/summary")
    assert response.status_code == 200
    body = response.get_json()
    assert set(body.keys()) >= {"tool", "status", "updated_at", "metrics", "details"}
    assert body["tool"] == "einstellungen"
    assert body["status"] in {"ok", "degraded", "error"}
    assert isinstance(body["updated_at"], str)
    assert isinstance(body["metrics"], dict)
    assert body["metrics"]["actions_available"] == 3
    assert body["metrics"]["write_actions_gated"] == 2
    assert body["details"]["actions"] == ["setting.read", "setting.update", "key.rotate"]
    gate = body["details"].get("approval_gate") or {}
    assert gate.get("write_confirm_required") is True
    assert gate.get("write_audit_required") is True


def test_einstellungen_health_contract(auth_client):
    response = auth_client.get("/api/einstellungen/health")
    assert response.status_code in {200, 503}
    body = response.get_json()
    assert set(body.keys()) >= {"tool", "status", "updated_at", "metrics", "details"}
    assert body["tool"] == "einstellungen"
    checks = body["details"].get("checks") or {}
    assert set(checks.keys()) == {"summary_contract", "backend_ready", "offline_safe"}
    assert body["details"]["actions"] == ["setting.read", "setting.update", "key.rotate"]
