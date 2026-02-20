from __future__ import annotations

from app.ai.clients.anthropic import AnthropicClient
from app.ai.clients.gemini import GeminiClient
from app.ai.clients.vllm import VLLMClient


def test_vllm_health_check(monkeypatch) -> None:
    client = VLLMClient(base_url="http://localhost:8000", model="demo")
    monkeypatch.setattr(
        "app.ai.clients.openai_compat.openai_compat_is_available",
        lambda **kwargs: True,
    )
    assert client.health_check() is True


def test_vllm_generate_text(monkeypatch) -> None:
    client = VLLMClient(base_url="http://localhost:8000", model="demo")
    monkeypatch.setattr(
        "app.ai.clients.openai_compat.openai_compat_chat",
        lambda **kwargs: {"message": {"content": "Hallo Welt", "tool_calls": []}},
    )
    out = client.generate_text(prompt="Test")
    assert out == "Hallo Welt"


def test_anthropic_health_check(monkeypatch) -> None:
    client = AnthropicClient(api_key="k")

    class _Resp:
        status_code = 200

    monkeypatch.setattr(
        "app.ai.clients.anthropic.requests.get", lambda *args, **kwargs: _Resp()
    )
    assert client.health_check() is True


def test_anthropic_generate_text_with_tools(monkeypatch) -> None:
    client = AnthropicClient(api_key="k")

    class _Resp:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "content": [
                    {"type": "text", "text": "ok"},
                    {
                        "type": "tool_use",
                        "id": "x1",
                        "name": "search",
                        "input": {"q": "abc"},
                    },
                ]
            }

    monkeypatch.setattr(
        "app.ai.clients.anthropic.requests.post", lambda *args, **kwargs: _Resp()
    )
    out = client.generate_text_with_tools(
        prompt="hallo",
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "search",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ],
    )
    assert (out["message"]["content"]) == "ok"
    assert out["message"]["tool_calls"][0]["function"]["name"] == "search"


def test_gemini_health_check(monkeypatch) -> None:
    client = GeminiClient(api_key="k")

    class _Resp:
        status_code = 200

    monkeypatch.setattr(
        "app.ai.clients.gemini.requests.get", lambda *args, **kwargs: _Resp()
    )
    assert client.health_check() is True


def test_gemini_generate_text(monkeypatch) -> None:
    client = GeminiClient(api_key="k")

    class _Resp:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "candidates": [{"content": {"parts": [{"text": "Hallo von Gemini"}]}}],
            }

    monkeypatch.setattr(
        "app.ai.clients.gemini.requests.post", lambda *args, **kwargs: _Resp()
    )
    out = client.generate_text(prompt="Test")
    assert out == "Hallo von Gemini"
