from __future__ import annotations

import importlib.util

import pytest

import app.web as webmod

from .pages.login_page import LoginPage

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("playwright") is None,
    reason="playwright not installed",
)


def _open_chat(page) -> None:
    page.click("#chatWidgetBtn")
    page.evaluate(
        """
        const drawer = document.getElementById('chatDrawer');
        if (drawer && drawer.classList.contains('hidden')) {
          drawer.classList.remove('hidden');
        }
        """
    )
    page.wait_for_selector("#chatWidgetInput", state="visible")


@pytest.mark.e2e
def test_ai_status_and_chat_smoke_with_mock(
    monkeypatch: pytest.MonkeyPatch,
    page,
    base_url: str,
) -> None:
    monkeypatch.setattr(webmod, "ollama_is_available", lambda **_: True)
    monkeypatch.setattr(webmod, "is_any_provider_available", lambda **_: True)
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
    _open_chat(page)
    page.wait_for_selector("#chatWidgetInput", state="visible")
    assert page.locator("#chatWidgetSend").is_enabled()

    response = page.request.post(
        f"{base_url}/api/ai/chat",
        data={"q": "Hallo KI"},
    )
    assert response.ok
    chat_payload = response.json()
    assert chat_payload["ok"] is True
    assert chat_payload["status"] == "ok"
    assert chat_payload["message"] == "Mock-Antwort fuer: Hallo KI"
