from __future__ import annotations

from typing import Any

import pytest

from app.ai import ollama_client
from app.ai.errors import OllamaBadResponse


class _Resp:
    def __init__(self, payload: Any, status_code: int = 200, text: str = "") -> None:
        self._payload = payload
        self.status_code = status_code
        self.text = text

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError("http_error")

    def json(self) -> Any:
        return self._payload


def test_ollama_status_and_models(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ollama_client.requests,
        "get",
        lambda *args, **kwargs: _Resp(
            {"models": [{"name": "llama3.1:8b"}, {"name": "mistral:7b"}]},
            status_code=200,
        ),
    )

    assert ollama_client.ollama_is_available() is True
    assert ollama_client.ollama_list_models() == ["llama3.1:8b", "mistral:7b"]


def test_ollama_chat_requires_message_dict(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ollama_client.requests,
        "post",
        lambda *args, **kwargs: _Resp({"message": "not_a_dict"}, status_code=200),
    )
    with pytest.raises(OllamaBadResponse):
        ollama_client.ollama_chat(messages=[{"role": "user", "content": "hi"}])


def test_ollama_chat_marks_model_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ollama_client.requests,
        "post",
        lambda *args, **kwargs: _Resp(
            {"error": "model 'missing-model' not found"},
            status_code=404,
        ),
    )
    with pytest.raises(OllamaBadResponse, match="ollama_model_not_found"):
        ollama_client.ollama_chat(
            messages=[{"role": "user", "content": "hi"}],
            model="missing-model",
        )
