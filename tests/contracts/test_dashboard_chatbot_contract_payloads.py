from __future__ import annotations


def test_dashboard_summary_declares_aggregation_contract(auth_client):
    response = auth_client.get("/api/dashboard/summary")
    assert response.status_code == 200

    body = response.get_json()
    assert body["tool"] == "dashboard"
    details = body["summary"]["details"]
    metrics = body["summary"]["metrics"]
    assert details["matrix_endpoint"] == "/api/dashboard/tool-matrix"
    assert details["aggregate_mode"] == "summary_only"
    assert metrics["total_tools"] == 10
    assert details["contract"]["read_only"] is True
    assert details["tenant"] == "KUKANILEA"


def test_chatbot_summary_declares_payload_aliases(auth_client):
    response = auth_client.get("/api/chatbot/summary")
    assert response.status_code == 200

    body = response.get_json()
    assert body["tool"] == "chatbot"

    details = body["summary"]["details"]
    metrics = body["summary"]["metrics"]
    contract = details["payload_contract"]
    assert contract["request_fields"] == ["message", "msg", "q"]
    assert contract["response_fields"] == ["ok", "response", "text", "actions", "requires_confirm"]
    assert details["summary_sources"] == ["dashboard", "tasks", "projects"]
    assert metrics["summary_sources"] == 3
    assert details["contract"]["read_only"] is True
    assert details["tenant"] == "KUKANILEA"


def test_chat_endpoint_standardizes_payload_aliases(auth_client, monkeypatch):
    import app.web as web

    monkeypatch.setattr(web, "agent_answer", lambda _msg: {"text": "pong"})

    with auth_client.session_transaction() as sess:
        sess["csrf_token"] = "csrf-test"

    response = auth_client.post(
        "/api/chat",
        json={"q": "ping"},
        headers={"X-CSRF-Token": "csrf-test"},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["text"] == "pong"
    assert body["response"] == "pong"


def test_chat_compact_accepts_message_alias(auth_client, monkeypatch):
    import app.web as web

    monkeypatch.setattr(web, "agent_answer", lambda *_args, **_kwargs: {"text": "bereit", "actions": []})

    with auth_client.session_transaction() as sess:
        sess["csrf_token"] = "csrf-test"

    response = auth_client.post(
        "/api/chat/compact",
        json={"msg": "hallo", "current_context": "/messenger"},
        headers={"X-CSRF-Token": "csrf-test"},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["response"] == "bereit"


def test_chat_accepts_nested_payload_alias(auth_client, monkeypatch):
    import app.web as web

    monkeypatch.setattr(web, "agent_answer", lambda _msg: {"response": "pong"})

    with auth_client.session_transaction() as sess:
        sess["csrf_token"] = "csrf-test"

    response = auth_client.post(
        "/api/chat",
        json={"payload": {"message": "ping"}},
        headers={"X-CSRF-Token": "csrf-test"},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["text"] == "pong"
    assert body["response"] == "pong"


def test_upload_summary_declares_intake_contract(auth_client):
    response = auth_client.get("/api/upload/summary")
    assert response.status_code == 200

    body = response.get_json()
    assert body["tool"] == "upload"

    intake_contract = body["summary"]["details"]["intake_contract"]
    assert intake_contract["normalize_endpoint"] == "/api/intake/normalize"
    assert intake_contract["execute_endpoint"] == "/api/intake/execute"
    assert intake_contract["requires_explicit_confirm"] is True
    assert intake_contract["execute_fields"] == ["envelope", "requires_confirm", "confirm"]
    assert "suggested_actions" in intake_contract["envelope_fields"]
    assert body["summary"]["details"]["tenant"] == "KUKANILEA"
