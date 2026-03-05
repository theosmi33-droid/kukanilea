from __future__ import annotations


def test_dashboard_summary_declares_aggregation_contract(auth_client):
    response = auth_client.get("/api/dashboard/summary")
    assert response.status_code == 200

    body = response.get_json()
    assert body["tool"] == "dashboard"
    assert body["details"]["matrix_endpoint"] == "/api/dashboard/tool-matrix"
    assert body["details"]["aggregate_mode"] == "summary_only"
    assert body["metrics"]["total_tools"] == 11
    assert body["details"]["contract"]["read_only"] is True
    assert body["details"]["tenant"] == "KUKANILEA"


def test_chatbot_summary_declares_payload_aliases(auth_client):
    response = auth_client.get("/api/chatbot/summary")
    assert response.status_code == 200

    body = response.get_json()
    assert body["tool"] == "chatbot"

    contract = body["details"]["payload_contract"]
    assert contract["request_fields"] == ["message", "msg", "q"]
    assert contract["response_fields"] == ["ok", "response", "text", "actions", "requires_confirm"]
    assert body["details"]["summary_sources"] == ["dashboard", "tasks", "projects"]
    assert body["metrics"]["summary_sources"] == 3
    assert body["details"]["contract"]["read_only"] is True
    assert body["details"]["tenant"] == "KUKANILEA"


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
