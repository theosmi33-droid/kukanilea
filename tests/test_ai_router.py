from __future__ import annotations

from app.ai.base import AIClient
from app.ai.provider_router import AIRouter, provider_specs_from_env


class _MockClient(AIClient):
    def __init__(self, name: str, healthy: bool, fail: bool = False) -> None:
        self._name = name
        self._healthy = healthy
        self._fail = fail

    @property
    def name(self) -> str:
        return self._name

    def generate_text(
        self,
        *,
        prompt: str,
        system: str | None = None,
        model: str | None = None,
        timeout_s: int = 90,
        **kwargs,
    ) -> str:
        if self._fail:
            raise RuntimeError("boom")
        return f"{self._name}:{prompt}"

    def generate_text_with_tools(
        self,
        *,
        prompt: str,
        tools=None,
        system: str | None = None,
        model: str | None = None,
        timeout_s: int = 90,
        messages=None,
        **kwargs,
    ):
        if self._fail:
            raise RuntimeError("boom")
        return {"message": {"content": f"{self._name}:ok", "tool_calls": []}}

    def health_check(self, timeout_s: int = 5) -> bool:
        return self._healthy


def test_router_selects_first_healthy_provider() -> None:
    router = AIRouter(
        [_MockClient("a", healthy=False), _MockClient("b", healthy=True)],
        health_ttl_s=1,
        retries_per_provider=1,
    )
    selected = router.get_available_provider()
    assert selected.name == "b"


def test_router_failover_on_runtime_error() -> None:
    router = AIRouter(
        [_MockClient("a", healthy=True, fail=True), _MockClient("b", healthy=True)],
        health_ttl_s=1,
        retries_per_provider=1,
    )
    out = router.generate_text_with_tools(
        messages=[{"role": "user", "content": "hallo"}],
        tools=[],
    )
    assert out["provider"] == "b"
    assert (out["response"]["message"]["content"]).startswith("b:")


def test_provider_specs_include_anthropic_and_gemini(monkeypatch) -> None:
    monkeypatch.setenv("KUKANILEA_AI_PROVIDER_ORDER", "anthropic,gemini")
    monkeypatch.setenv("KUKANILEA_ANTHROPIC_API_KEY", "a")
    monkeypatch.setenv("KUKANILEA_GEMINI_API_KEY", "g")
    specs = provider_specs_from_env()
    assert [s.provider_type for s in specs] == ["anthropic", "gemini"]
