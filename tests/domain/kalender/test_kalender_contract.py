from __future__ import annotations


def test_kalender_summary_contract(auth_client):
    response = auth_client.get("/api/kalender/summary")
    assert response.status_code == 200
    body = response.get_json()
    assert set(body.keys()) == {
        "status",
        "timestamp",
        "window_days",
        "events_next_7_days",
        "conflicts",
        "reminders_due",
        "metrics",
    }
    assert body["status"] in {"ok", "degraded", "error"}
    assert isinstance(body["timestamp"], str)
    assert isinstance(body["events_next_7_days"], list)
    assert isinstance(body["conflicts"], list)
    assert isinstance(body["reminders_due"], list)
    assert isinstance(body["metrics"], dict)


def test_kalender_health_contract(auth_client):
    response = auth_client.get("/api/kalender/health")
    assert response.status_code in {200, 503}
    body = response.get_json()
    assert set(body.keys()) >= {
        "status",
        "timestamp",
        "window_days",
        "events_next_7_days",
        "conflicts",
        "reminders_due",
        "metrics",
    }
    assert body["status"] in {"ok", "degraded", "error"}
    assert isinstance(body["timestamp"], str)
    assert isinstance(body["metrics"], dict)
    assert set(body["metrics"].keys()) >= {
        "backend_ready",
        "offline_safe",
        "offline_persistence",
        "sync_enabled",
    }
