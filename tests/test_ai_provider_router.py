from __future__ import annotations

import pytest

from app.ai import provider_router


def test_provider_order_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KUKANILEA_AI_PROVIDER_ORDER", raising=False)
    assert provider_router.provider_order_from_env() == ["ollama"]


def test_chat_with_fallback_uses_openai_compat(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KUKANILEA_AI_PROVIDER_ORDER", "openai_compat")
    monkeypatch.setenv("KUKANILEA_OPENAI_COMPAT_BASE_URL", "http://localhost:8000")
    monkeypatch.setenv("KUKANILEA_OPENAI_COMPAT_MODEL", "demo-model")
    monkeypatch.setattr(
        provider_router.OpenAICompatClient,
        "health_check",
        lambda self, timeout_s=5: True,
    )
    monkeypatch.setattr(
        provider_router.OpenAICompatClient,
        "generate_text_with_tools",
        lambda self, **kwargs: {"message": {"content": "ok", "tool_calls": []}},
    )

    out = provider_router.chat_with_fallback(
        messages=[{"role": "user", "content": "hallo"}],
        model="ignored",
    )
    assert out.get("ok") is True
    assert out.get("provider") == "openai_compat"
    response = out.get("response") or {}
    assert isinstance(response, dict)
    assert (response.get("message") or {}).get("content") == "ok"


def test_chat_with_fallback_respects_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KUKANILEA_AI_PROVIDER_ORDER", "ollama,openai_compat")
    monkeypatch.setenv(
        "KUKANILEA_AI_PROVIDER_POLICY_JSON",
        '{"roles":{"OFFICE":{"allow_providers":["openai_compat"]}}}',
    )
    monkeypatch.setenv("KUKANILEA_OPENAI_COMPAT_BASE_URL", "http://localhost:8000")
    monkeypatch.setenv("KUKANILEA_OPENAI_COMPAT_MODEL", "demo-model")
    monkeypatch.setattr(
        provider_router.OpenAICompatClient,
        "health_check",
        lambda self, timeout_s=5: True,
    )
    monkeypatch.setattr(
        provider_router.OpenAICompatClient,
        "generate_text_with_tools",
        lambda self, **kwargs: {"message": {"content": "policy-ok", "tool_calls": []}},
    )
    out = provider_router.chat_with_fallback(
        messages=[{"role": "user", "content": "hallo"}],
        model="ignored",
        tenant_id="TENANT_A",
        role="OFFICE",
    )
    assert out.get("ok") is True
    assert out.get("provider") == "openai_compat"
