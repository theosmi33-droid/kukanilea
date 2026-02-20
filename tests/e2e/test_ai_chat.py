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
    page.wait_for_selector("#chatDrawer:not(.hidden)", state="visible")
    page.wait_for_selector("#chatWidgetInput", state="visible")


@pytest.mark.e2e
def test_ai_chat_widget_with_mocked_orchestrator(
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
        lambda **_: {
            "status": "ok",
            "response": "Ich habe 1 Kontakt gefunden.",
            "conversation_id": "conv-e2e-1",
            "tool_used": ["search_contacts"],
        },
    )

    login = LoginPage(page, base_url)
    login.goto()
    login.login("e2e_admin", "e2e_admin")

    page.goto(f"{base_url}/")
    _open_chat(page)
    page.wait_for_selector("#chatWidgetInput", state="visible")
    assert page.locator("#chatWidgetSend").is_enabled()

    response = page.request.post(
        f"{base_url}/api/ai/chat",
        data={"q": "Suche nach Mueller"},
    )
    assert response.ok
    payload = response.json()
    assert payload["ok"] is True
    assert payload["status"] == "ok"
    assert payload["message"] == "Ich habe 1 Kontakt gefunden."
