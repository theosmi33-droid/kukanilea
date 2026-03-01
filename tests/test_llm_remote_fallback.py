import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))


def test_get_default_provider_uses_remote_when_enabled(monkeypatch):
    from app.agents import llm

    monkeypatch.setenv("OLLAMA_ENABLED", "0")
    monkeypatch.setenv("KUKANILEA_REMOTE_LLM_ENABLED", "1")
    monkeypatch.setenv("KUKANILEA_REMOTE_LLM_API_KEY", "test-key")
    monkeypatch.setenv("KUKANILEA_REMOTE_LLM_BASE", "https://example.invalid/v1")
    monkeypatch.setenv("KUKANILEA_REMOTE_LLM_MODEL", "test/model")

    monkeypatch.setattr(llm.OpenAICompatibleProvider, "_ping", lambda self: True)

    provider = llm.get_default_provider()
    assert provider.name == "remote"


def test_get_default_provider_falls_back_to_mock(monkeypatch):
    from app.agents import llm

    monkeypatch.setenv("OLLAMA_ENABLED", "0")
    monkeypatch.setenv("KUKANILEA_REMOTE_LLM_ENABLED", "0")
    monkeypatch.delenv("KUKANILEA_REMOTE_LLM_API_KEY", raising=False)

    provider = llm.get_default_provider()
    assert provider.name == "mock"
