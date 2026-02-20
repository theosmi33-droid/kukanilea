from __future__ import annotations

import time
from typing import Any

from .base import AIClient


class ProviderHealthCache:
    """Small in-memory TTL cache for provider health probes."""

    def __init__(self, ttl_s: int = 30) -> None:
        self._ttl_s = max(1, int(ttl_s))
        self._cache: dict[str, tuple[bool, float]] = {}

    def get(self, provider_name: str) -> bool | None:
        row = self._cache.get(str(provider_name))
        if not row:
            return None
        value, ts = row
        if (time.monotonic() - ts) > self._ttl_s:
            return None
        return bool(value)

    def set(self, provider_name: str, healthy: bool) -> None:
        self._cache[str(provider_name)] = (bool(healthy), time.monotonic())


def check_provider_health(
    provider: AIClient,
    *,
    cache: ProviderHealthCache | None = None,
    timeout_s: int = 5,
) -> bool:
    if cache is not None:
        cached = cache.get(provider.name)
        if cached is not None:
            return bool(cached)
    healthy = bool(provider.health_check(timeout_s=max(1, int(timeout_s))))
    if cache is not None:
        cache.set(provider.name, healthy)
    return healthy


def snapshot_health(
    providers: list[AIClient],
    *,
    cache: ProviderHealthCache | None = None,
    timeout_s: int = 5,
) -> dict[str, Any]:
    out: list[dict[str, Any]] = []
    for client in providers:
        out.append(
            {
                "provider": client.name,
                "healthy": check_provider_health(
                    client, cache=cache, timeout_s=max(1, int(timeout_s))
                ),
            }
        )
    return {"providers": out}
