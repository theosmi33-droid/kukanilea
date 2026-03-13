from __future__ import annotations

from flask import Flask

from app.routes.messenger import bp as messenger_bp


def _app() -> Flask:
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.secret_key = "test"

    @app.before_request
    def _auth_session():
        from flask import session

        session["user"] = "dev"
        session["role"] = "DEV"
        session["tenant_id"] = "KUKANILEA"
        session["csrf_token"] = "csrf-test"

    app.register_blueprint(messenger_bp)
    return app


def test_messenger_summary_endpoint_contract():
    client = _app().test_client()
    resp = client.get("/api/messenger/summary")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["tool"] == "messenger"
    assert body["status"] == "ok"
    assert body["details"]["confirm_gate"] is True


def test_messenger_health_endpoint_contract():
    client = _app().test_client()
    resp = client.get("/api/messenger/health")
    assert resp.status_code in {200, 503}
    body = resp.get_json()
    assert body["tool"] == "messenger"
    assert body["status"] in {"ok", "degraded", "error"}
    assert body["details"]["contract"]["kind"] == "health"
    assert set(body["details"]["checks"].keys()) == {"summary_contract", "backend_ready", "offline_safe"}


def test_chat_parsing_and_confirm_gate(monkeypatch):
    app = _app()
    client = app.test_client()

    import app.routes.messenger as messenger_route

    monkeypatch.setattr(
        messenger_route,
        "agent_answer",
        lambda _msg: {"ok": True, "text": "done", "actions": [{"type": "messenger_send"}]},
    )

    resp = client.post(
        "/api/chat",
        json={"msg": "schick das raus"},
        headers={"X-CSRF-Token": "csrf-test"},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["text"] == "done"
    assert body["response"] == "done"
    assert body["actions"][0]["confirm_required"] is True


def test_chat_structured_intake_contains_lead_fields_and_suggested_actions(monkeypatch):
    app = _app()
    client = app.test_client()

    import app.routes.messenger as messenger_route

    monkeypatch.setattr(
        messenger_route,
        "agent_answer",
        lambda _msg: {"ok": True, "text": "ok", "actions": [{"type": "create_task"}]},
    )

    resp = client.post(
        "/api/chat",
        json={"msg": "Ich bin Max Mustermann von Firma ACME. Mail an max@example.com und erstelle Aufgabe"},
        headers={"X-CSRF-Token": "csrf-test"},
    )

    assert resp.status_code == 200
    body = resp.get_json()
    intake = body["data"]["intake"]

    assert intake["lead_fields"]["contact_name"] == "Max Mustermann von Firma ACME"
    assert intake["lead_fields"]["contact_email"] == "max@example.com"
    assert intake["lead_fields"]["source"] == "chat"
    assert intake["suggested_next_actions"][0]["type"] == "create_task"
    assert intake["suggested_next_actions"][0]["confirm_required"] is True


def test_chat_structured_intake_extracts_phone_and_company(monkeypatch):
    app = _app()
    client = app.test_client()

    import app.routes.messenger as messenger_route

    monkeypatch.setattr(
        messenger_route,
        "agent_answer",
        lambda _msg: {"ok": True, "text": "ok", "actions": []},
    )

    resp = client.post(
        "/api/chat",
        json={"msg": "Ich bin Anna Meyer, Firma Bau AG. Ruf mich unter +49 171 1234567 an."},
        headers={"X-CSRF-Token": "csrf-test"},
    )

    assert resp.status_code == 200
    body = resp.get_json()
    intake = body["data"]["intake"]

    assert intake["lead_fields"]["contact_name"] == "Anna Meyer"
    assert intake["lead_fields"]["company"] == "Bau AG"
    assert intake["lead_fields"]["contact_phone"] == "+49 171 1234567"
    # No write intent in agent actions, but extracted lead info must still be present.
    assert isinstance(intake["suggested_next_actions"], list)


def test_chat_structured_intake_derives_fallback_actions_from_keywords(monkeypatch):
    app = _app()
    client = app.test_client()

    import app.routes.messenger as messenger_route

    monkeypatch.setattr(
        messenger_route,
        "agent_answer",
        lambda _msg: {"ok": True, "text": "ok", "actions": []},
    )

    resp = client.post(
        "/api/chat",
        json={"msg": "Bitte erstelle eine Aufgabe, plane einen Termin und sende eine Nachricht per Mail."},
        headers={"X-CSRF-Token": "csrf-test"},
    )

    assert resp.status_code == 200
    body = resp.get_json()
    intake = body["data"]["intake"]
    action_types = [item["type"] for item in intake["suggested_next_actions"]]

    assert "create_task" in action_types
    assert "create_appointment" in action_types
    assert "messenger_send" in action_types
    assert all(bool(item["confirm_required"]) for item in intake["suggested_next_actions"])
