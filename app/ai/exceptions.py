from __future__ import annotations


class AIProviderError(RuntimeError):
    """Base error for provider/router failures."""


class ProviderUnavailable(AIProviderError):
    """Raised when a provider cannot serve request."""


class NoProviderAvailable(AIProviderError):
    """Raised when no configured provider is healthy."""
