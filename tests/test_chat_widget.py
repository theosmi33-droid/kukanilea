from __future__ import annotations

from app import create_app, web


def _login(client) -> None:
    with client.session_transaction() as sess:
        sess["user"] = "dev"
        sess["role"] = "ADMIN"
        sess["tenant_id"] = "KUKANILEA"


def test_chat_widget_present_for_authenticated_user() -> None:
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    client = app.test_client()
    _login(client)
    res = client.get("/")
    assert res.status_code == 200
    assert b"chatWidgetBtn" in res.data


def test_chat_api_hx_request_returns_html_fragment(monkeypatch) -> None:
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    client = app.test_client()
    _login(client)

    monkeypatch.setattr(web, "agent_answer", lambda msg: {"text": "Antwort"})

    res = client.post(
        "/api/chat",
        data={"msg": "Hallo"},
        headers={"HX-Request": "true"},
    )
    assert res.status_code == 200
    assert b"Antwort" in res.data
    assert b"<div" in res.data
