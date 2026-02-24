from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from .base import AIClient
from .clients import (
    AnthropicClient,
    GeminiClient,
    GroqClient,
    LMStudioClient,
    OllamaProviderClient,
    OpenAICompatClient,
    VLLMClient,
)
from .exceptions import NoProviderAvailable, ProviderUnavailable
from .health import ProviderHealthCache, check_provider_health, snapshot_health
from .policy import effective_rule_public, filter_provider_specs

DEFAULT_PROVIDER_ORDER = "ollama"


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.environ.get(key, str(default)))
    except Exception:
        return int(default)


def provider_order_from_env() -> list[str]:
    raw = str(
        os.environ.get("KUKANILEA_AI_PROVIDER_ORDER", "")
    ).strip()
    if raw:
        out: list[str] = []
        for part in raw.split(","):
            p = str(part or "").strip().lower()
            if p and p not in out:
                out.append(p)
        return out
    
    # Adaptive Default: Ollama first, then fallbacks if keys present
    order = ["ollama"]
    
    # Check for various fallback keys
    if os.environ.get("OPENAI_API_KEY") or os.environ.get("KUKANILEA_OPENAI_COMPAT_API_KEY"):
        order.append("openai_compat")
    if os.environ.get("GROQ_API_KEY"):
        order.append("groq")
    if os.environ.get("ANTHROPIC_API_KEY"):
        order.append("anthropic")
    if os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"):
        order.append("gemini")
        
    return order


@dataclass(frozen=True)
class ProviderSpec:
    provider_type: str
    priority: int
    base_url: str = ""
    model: str = ""
    api_key: str = ""
    timeout_s: int = 60

    def as_dict(self) -> dict[str, Any]:
        return {
            "type": self.provider_type,
            "priority": self.priority,
            "base_url": self.base_url,
            "model": self.model,
            "api_key_set": bool(self.api_key),
            "timeout_s": self.timeout_s,
        }


def _provider_specs_from_json_env() -> list[ProviderSpec]:
    raw = str(os.environ.get("KUKANILEA_AI_PROVIDERS_JSON", "")).strip()
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except Exception:
        return []
    if not isinstance(parsed, list):
        return []
    out: list[ProviderSpec] = []
    for idx, row in enumerate(parsed):
        if not isinstance(row, dict):
            continue
        provider_type = str(row.get("type") or "").strip().lower()
        if not provider_type:
            continue
        try:
            priority = int(row.get("priority", idx + 1))
        except Exception:
            priority = idx + 1
        out.append(
            ProviderSpec(
                provider_type=provider_type,
                priority=priority,
                base_url=str(row.get("base_url") or row.get("url") or "").strip(),
                model=str(row.get("model") or "").strip(),
                api_key=str(row.get("api_key") or "").strip(),
                timeout_s=max(1, int(row.get("timeout_s") or 60)),
            )
        )
    out.sort(key=lambda s: s.priority)
    return out


def _legacy_spec(name: str, priority: int) -> ProviderSpec | None:
    provider = str(name or "").strip().lower()
    if provider == "ollama":
        return ProviderSpec(
            provider_type="ollama",
            priority=priority,
            base_url=str(
                os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
            ).strip(),
            model=str(os.environ.get("OLLAMA_MODEL", "llama3.1:8b")).strip(),
            timeout_s=max(1, _env_int("OLLAMA_TIMEOUT", 300)),
        )
    if provider == "vllm":
        return ProviderSpec(
            provider_type="vllm",
            priority=priority,
            base_url=str(
                os.environ.get("KUKANILEA_VLLM_BASE_URL", "http://127.0.0.1:8000")
            ).strip(),
            model=str(
                os.environ.get(
                    "KUKANILEA_VLLM_MODEL", "meta-llama/Llama-3.1-8B-Instruct"
                )
            ).strip(),
            api_key=str(os.environ.get("KUKANILEA_VLLM_API_KEY", "")).strip(),
            timeout_s=max(1, _env_int("KUKANILEA_VLLM_TIMEOUT", 60)),
        )
    if provider in {"lmstudio", "lm_studio"}:
        return ProviderSpec(
            provider_type="lmstudio",
            priority=priority,
            base_url=str(
                os.environ.get("KUKANILEA_LMSTUDIO_BASE_URL", "http://127.0.0.1:1234")
            ).strip(),
            model=str(
                os.environ.get("KUKANILEA_LMSTUDIO_MODEL", "local-model")
            ).strip(),
            timeout_s=max(1, _env_int("KUKANILEA_LMSTUDIO_TIMEOUT", 60)),
        )
    if provider == "groq":
        return ProviderSpec(
            provider_type="groq",
            priority=priority,
            base_url=str(
                os.environ.get(
                    "KUKANILEA_GROQ_BASE_URL", "https://api.groq.com/openai/v1"
                )
            ).strip(),
            model=str(
                os.environ.get("KUKANILEA_GROQ_MODEL", "llama-3.3-70b-versatile")
            ).strip(),
            api_key=str(
                os.environ.get("KUKANILEA_GROQ_API_KEY")
                or os.environ.get("GROQ_API_KEY")
                or ""
            ).strip(),
            timeout_s=max(1, _env_int("KUKANILEA_GROQ_TIMEOUT", 30)),
        )
    if provider == "anthropic":
        return ProviderSpec(
            provider_type="anthropic",
            priority=priority,
            base_url=str(
                os.environ.get(
                    "KUKANILEA_ANTHROPIC_BASE_URL", "https://api.anthropic.com"
                )
            ).strip(),
            model=str(
                os.environ.get("KUKANILEA_ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")
            ).strip(),
            api_key=str(
                os.environ.get("KUKANILEA_ANTHROPIC_API_KEY")
                or os.environ.get("ANTHROPIC_API_KEY")
                or ""
            ).strip(),
            timeout_s=max(1, _env_int("KUKANILEA_ANTHROPIC_TIMEOUT", 60)),
        )
    if provider == "gemini":
        return ProviderSpec(
            provider_type="gemini",
            priority=priority,
            base_url=str(
                os.environ.get(
                    "KUKANILEA_GEMINI_BASE_URL",
                    "https://generativelanguage.googleapis.com",
                )
            ).strip(),
            model=str(
                os.environ.get("KUKANILEA_GEMINI_MODEL", "gemini-1.5-flash")
            ).strip(),
            api_key=str(
                os.environ.get("KUKANILEA_GEMINI_API_KEY")
                or os.environ.get("GEMINI_API_KEY")
                or os.environ.get("GOOGLE_API_KEY")
                or ""
            ).strip(),
            timeout_s=max(1, _env_int("KUKANILEA_GEMINI_TIMEOUT", 60)),
        )
    if provider in {"openai_compat", "openai-compatible"}:
        return ProviderSpec(
            provider_type="openai_compat",
            priority=priority,
            base_url=str(
                os.environ.get("KUKANILEA_OPENAI_COMPAT_BASE_URL", "")
            ).strip(),
            model=str(
                os.environ.get("KUKANILEA_OPENAI_COMPAT_MODEL", "gpt-4o-mini")
            ).strip(),
            api_key=str(os.environ.get("KUKANILEA_OPENAI_COMPAT_API_KEY", "")).strip(),
            timeout_s=max(1, _env_int("KUKANILEA_OPENAI_COMPAT_TIMEOUT", 60)),
        )
    if provider in {"openai_compat_fallback", "openai-compatible-fallback"}:
        return ProviderSpec(
            provider_type="openai_compat_fallback",
            priority=priority,
            base_url=str(
                os.environ.get("KUKANILEA_OPENAI_COMPAT_BASE_URL_FALLBACK", "")
            ).strip(),
            model=str(
                os.environ.get(
                    "KUKANILEA_OPENAI_COMPAT_MODEL_FALLBACK",
                    os.environ.get("KUKANILEA_OPENAI_COMPAT_MODEL", "gpt-4o-mini"),
                )
            ).strip(),
            api_key=str(
                os.environ.get("KUKANILEA_OPENAI_COMPAT_API_KEY_FALLBACK", "")
            ).strip(),
            timeout_s=max(
                1,
                _env_int(
                    "KUKANILEA_OPENAI_COMPAT_TIMEOUT_FALLBACK",
                    _env_int("KUKANILEA_OPENAI_COMPAT_TIMEOUT", 60),
                ),
            ),
        )
    return None


def provider_specs_from_env(
    order: list[str] | None = None,
    *,
    tenant_id: str | None = None,
    role: str | None = None,
) -> list[ProviderSpec]:
    specs = _provider_specs_from_json_env()
    if not specs:
        providers = order or provider_order_from_env()
        out: list[ProviderSpec] = []
        for idx, name in enumerate(providers):
            row = _legacy_spec(name, idx + 1)
            if row is not None:
                out.append(row)
        specs = out
    return list(filter_provider_specs(specs=specs, tenant_id=tenant_id, role=role))


def create_clients_from_specs(specs: list[ProviderSpec]) -> list[AIClient]:
    clients: list[AIClient] = []
    for spec in sorted(specs, key=lambda s: s.priority):
        ptype = spec.provider_type
        if ptype == "ollama":
            clients.append(
                OllamaProviderClient(
                    base_url=spec.base_url or "http://127.0.0.1:11434",
                    model=spec.model or "llama3.1:8b",
                    timeout_s=spec.timeout_s,
                )
            )
            continue
        if ptype == "vllm":
            clients.append(
                VLLMClient(
                    base_url=spec.base_url or "http://127.0.0.1:8000",
                    model=spec.model or "meta-llama/Llama-3.1-8B-Instruct",
                    api_key=spec.api_key,
                    timeout_s=spec.timeout_s,
                )
            )
            continue
        if ptype in {"lmstudio", "lm_studio"}:
            clients.append(
                LMStudioClient(
                    base_url=spec.base_url or "http://127.0.0.1:1234",
                    model=spec.model or "local-model",
                    api_key=spec.api_key,
                    timeout_s=spec.timeout_s,
                )
            )
            continue
        if ptype == "groq":
            clients.append(
                GroqClient(
                    base_url=spec.base_url or "https://api.groq.com/openai/v1",
                    model=spec.model or "llama-3.3-70b-versatile",
                    api_key=spec.api_key,
                    timeout_s=spec.timeout_s,
                )
            )
            continue
        if ptype == "anthropic":
            clients.append(
                AnthropicClient(
                    base_url=spec.base_url or "https://api.anthropic.com",
                    model=spec.model or "claude-3-5-sonnet-latest",
                    api_key=spec.api_key,
                    timeout_s=spec.timeout_s,
                )
            )
            continue
        if ptype == "gemini":
            clients.append(
                GeminiClient(
                    base_url=spec.base_url
                    or "https://generativelanguage.googleapis.com",
                    model=spec.model or "gemini-1.5-flash",
                    api_key=spec.api_key,
                    timeout_s=spec.timeout_s,
                )
            )
            continue
        if ptype in {"openai_compat", "openai-compatible"}:
            clients.append(
                OpenAICompatClient(
                    provider_name="openai_compat",
                    base_url=spec.base_url,
                    model=spec.model or "gpt-4o-mini",
                    api_key=spec.api_key,
                    timeout_s=spec.timeout_s,
                )
            )
            continue
        if ptype in {"openai_compat_fallback", "openai-compatible-fallback"}:
            clients.append(
                OpenAICompatClient(
                    provider_name="openai_compat_fallback",
                    base_url=spec.base_url,
                    model=spec.model or "gpt-4o-mini",
                    api_key=spec.api_key,
                    timeout_s=spec.timeout_s,
                )
            )
            continue
    return clients


class AIRouter:
    """Priority-based provider router with health checks and failover."""

    def __init__(
        self,
        providers: list[AIClient],
        *,
        health_ttl_s: int = 30,
        retries_per_provider: int = 1,
    ) -> None:
        self.providers = list(providers or [])
        self.health_cache = ProviderHealthCache(ttl_s=max(1, int(health_ttl_s)))
        self.retries_per_provider = max(1, int(retries_per_provider))

    def _healthy(self, provider: AIClient) -> bool:
        return check_provider_health(provider, cache=self.health_cache, timeout_s=5)

    def get_available_provider(self) -> AIClient:
        for provider in self.providers:
            if self._healthy(provider):
                return provider
        raise NoProviderAvailable("no_provider_available")

    def health_snapshot(self) -> dict[str, Any]:
        return snapshot_health(self.providers, cache=self.health_cache, timeout_s=5)

    def generate_text(
        self,
        *,
        prompt: str,
        system: str | None = None,
        model: str | None = None,
        timeout_s: int = 90,
    ) -> dict[str, Any]:
        if not self.providers:
            raise NoProviderAvailable("no_provider_configured")
        errors: list[str] = []
        for provider in self.providers:
            if not self._healthy(provider):
                errors.append(f"{provider.name}:unhealthy")
                continue
            for _ in range(self.retries_per_provider):
                try:
                    text = provider.generate_text(
                        prompt=prompt,
                        system=system,
                        model=model,
                        timeout_s=timeout_s,
                    )
                    return {"provider": provider.name, "text": text}
                except Exception:
                    self.health_cache.set(provider.name, False)
                    errors.append(f"{provider.name}:request_failed")
                    continue
        raise ProviderUnavailable(
            ",".join(errors) if errors else "no_provider_available"
        )

    def generate_text_with_tools(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        timeout_s: int = 90,
    ) -> dict[str, Any]:
        if not self.providers:
            raise NoProviderAvailable("no_provider_configured")
        errors: list[str] = []
        for provider in self.providers:
            if not self._healthy(provider):
                errors.append(f"{provider.name}:unhealthy")
                continue
            for _ in range(self.retries_per_provider):
                try:
                    response = provider.generate_text_with_tools(
                        prompt="",
                        messages=messages,
                        tools=tools,
                        model=model,
                        timeout_s=timeout_s,
                    )
                    return {"provider": provider.name, "response": response}
                except Exception:
                    self.health_cache.set(provider.name, False)
                    errors.append(f"{provider.name}:request_failed")
                    continue
        raise ProviderUnavailable(
            ",".join(errors) if errors else "no_provider_available"
        )


def create_router_from_env(
    order: list[str] | None = None,
    *,
    tenant_id: str | None = None,
    role: str | None = None,
) -> AIRouter:
    specs = provider_specs_from_env(order=order, tenant_id=tenant_id, role=role)
    clients = create_clients_from_specs(specs)
    retries = max(1, _env_int("KUKANILEA_AI_PROVIDER_RETRIES", 1))
    ttl = max(1, _env_int("KUKANILEA_AI_HEALTH_TTL_SECONDS", 30))
    return AIRouter(clients, health_ttl_s=ttl, retries_per_provider=retries)


def provider_specs_public(
    order: list[str] | None = None,
    *,
    tenant_id: str | None = None,
    role: str | None = None,
) -> list[dict[str, Any]]:
    return [
        row.as_dict()
        for row in provider_specs_from_env(order=order, tenant_id=tenant_id, role=role)
    ]


def provider_health_snapshot(
    order: list[str] | None = None,
    *,
    tenant_id: str | None = None,
    role: str | None = None,
) -> dict[str, Any]:
    router = create_router_from_env(order=order, tenant_id=tenant_id, role=role)
    return router.health_snapshot()


def provider_effective_policy(
    *,
    tenant_id: str | None,
    role: str | None,
) -> dict[str, Any]:
    return effective_rule_public(tenant_id=tenant_id, role=role)


def is_any_provider_available(
    order: list[str] | None = None,
    *,
    tenant_id: str | None = None,
    role: str | None = None,
) -> bool:
    router = create_router_from_env(order=order, tenant_id=tenant_id, role=role)
    for provider in router.providers:
        if router._healthy(provider):
            return True
    return False


def chat_with_fallback(
    *,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    model: str | None = None,
    timeout_s: int = 90,
    tenant_id: str | None = None,
    role: str | None = None,
) -> dict[str, Any]:
    """
    Versucht Inferenz über den primären Provider (meist Ollama), 
    weicht bei Fehlern auf Alternativen oder Cloud aus.
    """
    router = create_router_from_env(tenant_id=tenant_id, role=role)
    try:
        routed = router.generate_text_with_tools(
            messages=messages,
            tools=tools,
            model=model,
            timeout_s=timeout_s,
        )
        return {
            "ok": True,
            "provider": str(routed.get("provider") or ""),
            "response": routed.get("response"),
        }
    except (NoProviderAvailable, ProviderUnavailable, Exception) as exc:
        logging.warning(f"KI-Inferenz fehlgeschlagen: {exc}. Prüfe Fallback...")
        
        # Falls OpenAI Key vorhanden, könnte hier ein direkter Notfall-Call stehen
        # Aber der AIRouter deckt das bereits über die Prioritätenliste ab.
        # Wenn wir hier landen, ist wirklich gar nichts erreichbar.
        
        return {
            "ok": False,
            "provider": "",
            "response": None,
            "message": "KI-Assistent ist derzeit offline. Bitte 'ollama serve' starten oder API-Key prüfen.",
            "error_code": "AI_OFFLINE"
        }
