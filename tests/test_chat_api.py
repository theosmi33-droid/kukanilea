from __future__ import annotations

from app import create_app, web
from kukanilea.llm import MockProvider
from kukanilea.orchestrator import Orchestrator


class DummyCore:
    def assistant_search(self, query, kdnr="", limit=8, role="ADMIN", tenant_id=""):
        return [
            {
                "doc_id": "abc123def456",
                "kdnr": kdnr or "12393",
                "doctype": "RECHNUNG",
                "doc_date": "2024-06-01",
                "file_name": "rechnung.pdf",
                "file_path": "/tmp/rechnung.pdf",
                "preview": "...",
            }
        ]


def test_chat_api_ok(monkeypatch):
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    orch = Orchestrator(DummyCore(), llm_provider=MockProvider())
    monkeypatch.setattr(web, "ORCHESTRATOR", orch)

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user"] = "dev"
        sess["role"] = "ADMIN"
        sess["tenant_id"] = "KUKANILEA"

    res = client.post("/api/chat", json={"q": "rechnung"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["ok"] is True
    assert "message" in data
    assert "actions" in data
    assert "suggestions" in data


def test_api_health_no_redirect():
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    client = app.test_client()
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.get_json()
    assert data["ok"] is True


def test_api_chat_requires_auth(monkeypatch):
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    orch = Orchestrator(DummyCore(), llm_provider=MockProvider())
    monkeypatch.setattr(web, "ORCHESTRATOR", orch)
    client = app.test_client()
    res = client.post("/api/chat", json={"q": "rechnung"})
    assert res.status_code == 401
    data = res.get_json()
    assert data["ok"] is False
