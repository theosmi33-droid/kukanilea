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


def test_upload_ingest_respects_artifact_quota(auth_client, monkeypatch):
    monkeypatch.setattr("app.modules.upload.ingestion.INGEST_ARTIFACT_QUOTA_BYTES", 10)
    response = auth_client.post(
        "/api/upload/ingest",
        json={"source": "text", "text": "this payload is too large"},
    )
    assert response.status_code == 403
    body = response.get_json()
    assert body["error"] == "quota_exceeded"


def test_upload_rejects_missing_file_with_error_and_message(auth_client):
    with auth_client.session_transaction() as sess:
        sess["csrf_token"] = "csrf-test"

    response = auth_client.post(
        "/upload",
        data={"csrf_token": "csrf-test"},
        headers={"X-CSRF-Token": "csrf-test", "Accept": "application/json"},
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body["error"] == "no_file"
    assert isinstance(body.get("message"), str)
    assert body["message"]


def test_upload_rejects_invalid_stream_with_error_and_message(auth_client, monkeypatch):
    from io import BytesIO

    with auth_client.session_transaction() as sess:
        sess["csrf_token"] = "csrf-test"

    monkeypatch.setattr(
        "app.core.upload_pipeline.save_upload_stream",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("invalid_upload_stream")),
    )

    response = auth_client.post(
        "/upload",
        data={"file": (BytesIO(b"bad"), "broken.pdf"), "csrf_token": "csrf-test"},
        headers={"X-CSRF-Token": "csrf-test", "Accept": "application/json"},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body["error"] == "invalid_upload_stream"
    assert isinstance(body.get("message"), str)
    assert body["message"]
