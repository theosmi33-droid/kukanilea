from __future__ import annotations

from pathlib import Path

import app.web as webmod
import kukanilea_core_v3_fixed as core
from app import create_app
from app.ai.memory import save_conversation
from app.config import Config


def _login(client) -> None:
    with client.session_transaction() as sess:
        sess["user"] = "dev"
        sess["role"] = "ADMIN"
        sess["tenant_id"] = "KUKANILEA"


def _set_core_db(tmp_path: Path, app=None) -> Path:
    db_path = tmp_path / "core.sqlite3"
    webmod.core.DB_PATH = db_path
    core.DB_PATH = db_path
    Config.CORE_DB = db_path
    if app is not None:
        app.config["CORE_DB"] = db_path
    return db_path


def test_api_ai_status(monkeypatch) -> None:
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    client = app.test_client()
    _login(client)

    monkeypatch.setattr(webmod, "ollama_is_available", lambda **kwargs: True)
    monkeypatch.setattr(webmod, "is_any_provider_available", lambda **kwargs: True)
    monkeypatch.setattr(
        webmod,
        "ollama_list_models",
        lambda **kwargs: ["llama3.1:8b", "mistral:7b"],
    )
    res = client.get("/api/ai/status")
    assert res.status_code == 200
    payload = res.get_json() or {}
    assert payload.get("available") is True
    assert payload.get("any_provider_available") is True
    assert payload.get("ollama_available") is True
    assert "llama3.1:8b" in (payload.get("models") or [])


def test_api_ai_chat_success(monkeypatch) -> None:
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    client = app.test_client()
    _login(client)

    monkeypatch.setattr(
        webmod,
        "ai_process_message",
        lambda **kwargs: {
            "status": "ok",
            "response": "Hallo von KI",
            "conversation_id": "conv-123",
            "tool_used": ["search_contacts"],
        },
    )
    res = client.post("/api/ai/chat", json={"q": "hallo"})
    assert res.status_code == 200
    payload = res.get_json() or {}
    assert payload.get("status") == "ok"
    assert payload.get("message") == "Hallo von KI"
    assert payload.get("conversation_id") == "conv-123"


def test_api_ai_confirm_tool_success(monkeypatch) -> None:
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    client = app.test_client()
    _login(client)

    monkeypatch.setattr(
        webmod,
        "ai_confirm_tool_call",
        lambda **kwargs: {
            "status": "ok",
            "response": "Bestaetigte Aktion ausgefuehrt.",
            "conversation_id": "conv-confirm-1",
            "tool_used": ["create_task"],
            "result": {"task_id": 12},
        },
    )
    res = client.post("/api/ai/confirm_tool", json={"token": "signed-token"})
    assert res.status_code == 200
    payload = res.get_json() or {}
    assert payload.get("ok") is True
    assert payload.get("status") == "ok"
    assert payload.get("conversation_id") == "conv-confirm-1"
    assert payload.get("tool_used") == ["create_task"]


def test_api_ai_feedback_route(tmp_path: Path) -> None:
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    _set_core_db(tmp_path, app=app)
    client = app.test_client()
    _login(client)

    conv_id = save_conversation(
        tenant_id="KUKANILEA",
        user_id="dev",
        user_message="Hallo",
        assistant_response="Hi",
        tools_used=[],
    )
    assert conv_id

    res = client.post(
        "/api/ai/feedback",
        json={"conversation_id": conv_id, "rating": "positive"},
    )
    assert res.status_code == 200
    payload = res.get_json() or {}
    assert payload.get("ok") is True
