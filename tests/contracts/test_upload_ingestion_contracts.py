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
    assert set(body.keys()) >= {"source", "ts", "tenant", "entities", "suggested_tasks", "audit", "classification", "extraction", "proposed_actions"}
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



def test_upload_ingest_contract_includes_classification_and_actions(auth_client):
    response = auth_client.post(
        "/api/upload/ingest",
        data={"source": "pdf", "text": "Project: Test\nTask: Follow-up"},
    )
    assert response.status_code == 200

    body = response.get_json()
    assert set(body["classification"].keys()) >= {"label", "confidence", "scores", "rationale", "version"}
    assert set(body["extraction"].keys()) >= {"strategy", "warnings", "text_length"}
    assert isinstance(body["proposed_actions"], list)
