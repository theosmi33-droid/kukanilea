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
    assert body["summary"]["details"]["confirm_gate"] is True


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
