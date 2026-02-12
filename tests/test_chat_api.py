from __future__ import annotations

from app import create_app, web


def test_chat_api_ok(monkeypatch):
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")

    monkeypatch.setattr(
        web,
        "agent_answer",
        lambda msg: {
            "text": "ok",
            "facts": [{"text": "f1", "meta": {"kind": "task", "pk": 1}, "score": 0.1}],
            "action": None,
        },
    )

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user"] = "dev"
        sess["role"] = "ADMIN"
        sess["tenant_id"] = "KUKANILEA"

    res = client.post("/api/chat", json={"q": "rechnung"})
    assert res.status_code == 200
    data = res.get_json()
    assert set(data.keys()) == {"text", "facts", "action"}


def test_api_health_no_redirect():
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    client = app.test_client()
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.get_json()
    assert data["ok"] is True


def test_api_chat_requires_auth():
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    client = app.test_client()
    res = client.post("/api/chat", json={"q": "rechnung"})
    assert res.status_code == 401
    data = res.get_json()
    assert data["ok"] is False
