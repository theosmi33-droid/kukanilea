from __future__ import annotations

import pytest

from app.ai.clients import ollama as ollama_module
from app.ai.clients.ollama import OllamaProviderClient
from app.ai.errors import OllamaBadResponse, OllamaUnavailable


def test_default_model_fallbacks_are_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("KUKANILEA_OLLAMA_MODEL_FALLBACKS", raising=False)
    client = OllamaProviderClient(model="llama3.1:8b")
    assert client.model_candidates == ["llama3.1:8b", "llama3.2:3b", "qwen2.5:3b"]


def test_generate_text_uses_model_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def _fake_chat(*, model=None, **kwargs):
        calls.append(str(model))
        if str(model) == "llama3.1:8b":
            raise OllamaBadResponse("ollama_model_not_found")
        return {"message": {"content": "ok-fallback"}}

    monkeypatch.setattr(ollama_module, "ollama_chat", _fake_chat)
    client = OllamaProviderClient(
        model="llama3.1:8b",
        fallback_models=["llama3.2:3b"],
    )

    out = client.generate_text(prompt="hallo")
    assert out == "ok-fallback"
    assert calls == ["llama3.1:8b", "llama3.2:3b"]


def test_generate_text_with_tools_uses_requested_model_then_fallbacks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def _fake_chat(*, model=None, **kwargs):
        calls.append(str(model))
        if str(model) in {"custom:1b", "llama3.1:8b"}:
            raise OllamaBadResponse("ollama_model_not_found")
        return {"message": {"content": "ok"}, "tool_calls": []}

    monkeypatch.setattr(ollama_module, "ollama_chat", _fake_chat)
    client = OllamaProviderClient(
        model="llama3.1:8b",
        fallback_models=["llama3.2:3b"],
    )

    out = client.generate_text_with_tools(
        prompt="hallo",
        tools=[{"type": "function", "function": {"name": "search_documents"}}],
        model="custom:1b",
    )
    assert isinstance(out, dict)
    assert calls == ["custom:1b", "llama3.1:8b", "llama3.2:3b"]


def test_generate_text_fails_fast_when_ollama_unreachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def _fake_chat(*, model=None, **kwargs):
        calls.append(str(model))
        raise OllamaUnavailable("ollama_chat_unreachable")

    monkeypatch.setattr(ollama_module, "ollama_chat", _fake_chat)
    client = OllamaProviderClient(
        model="llama3.1:8b",
        fallback_models=["llama3.2:3b"],
    )

    with pytest.raises(OllamaUnavailable):
        client.generate_text(prompt="hallo")
    assert calls == ["llama3.1:8b"]
