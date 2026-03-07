from __future__ import annotations

import urllib.request

from app.ai.embeddings import generate_embedding


def test_generate_embedding_skips_network_when_ollama_disabled(monkeypatch) -> None:
    calls = {"count": 0}

    def _forbidden(*args, **kwargs):
        calls["count"] += 1
        raise AssertionError("urlopen must not be called when OLLAMA_ENABLED=0")

    monkeypatch.setenv("OLLAMA_ENABLED", "0")
    monkeypatch.setattr(urllib.request, "urlopen", _forbidden)

    assert generate_embedding("hello world") is None
    assert calls["count"] == 0
