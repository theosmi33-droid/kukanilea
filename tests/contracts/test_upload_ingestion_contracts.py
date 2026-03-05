from __future__ import annotations


def test_upload_ingest_contract_payload(auth_client):
    response = auth_client.post(
        "/api/upload/ingest",
        json={
            "source": "text",
            "text": "Project: Solar Roof\nTask: Create offer draft",
            "metadata": {"channel": "mail"},
        },
    )
    assert response.status_code == 200

    body = response.get_json()
    assert set(body.keys()) >= {"source", "ts", "tenant", "entities", "suggested_tasks", "audit"}
    assert body["source"] == "text"
    assert body["tenant"] == "KUKANILEA"
    assert isinstance(body["entities"], list)
    assert isinstance(body["suggested_tasks"], list)
    assert isinstance(body["audit"].get("artifact_hash"), str)


def test_upload_healthcheck_available(auth_client):
    response = auth_client.get("/api/upload/health")
    assert response.status_code in {200, 503}

    body = response.get_json()
    assert body["tool"] == "upload"
    checks = body.get("details", {}).get("checks", {})
    assert set(checks.keys()) == {"summary_contract", "backend_ready", "offline_safe"}
