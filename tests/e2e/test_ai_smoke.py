from __future__ import annotations

import importlib.util

import pytest

import app.web as webmod

from .pages.login_page import LoginPage

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("playwright") is None,
    reason="playwright not installed",
)


@pytest.mark.e2e
def test_ai_status_and_chat_smoke_with_mock(
    monkeypatch: pytest.MonkeyPatch,
    page,
    base_url: str,
) -> None:
    monkeypatch.setattr(webmod, "ollama_is_available", lambda **_: True)
    monkeypatch.setattr(webmod, "ollama_list_models", lambda **_: ["llama3.1:8b"])
    monkeypatch.setattr(
        webmod,
        "ai_process_message",
        lambda **kwargs: {
            "status": "ok",
            "response": f"Mock-Antwort fuer: {kwargs.get('user_message', '')}",
            "conversation_id": "conv-smoke-1",
            "tool_used": [],
        },
    )

    login = LoginPage(page, base_url)
    login.goto()
    login.login("e2e_admin", "e2e_admin")

    status = page.request.get(f"{base_url}/api/ai/status")
    assert status.ok
    payload = status.json()
    assert payload["available"] is True

    page.goto(f"{base_url}/")
    page.click("#chatWidgetBtn")
    page.fill("#chatWidgetInput", "Hallo KI")
    page.click("#chatWidgetSend")

    msgs = page.locator("#chatWidgetMsgs")
    msgs.wait_for(timeout=5000)
    assert "Mock-Antwort fuer: Hallo KI" in str(msgs.text_content())
