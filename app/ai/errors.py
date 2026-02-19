from __future__ import annotations


class OllamaUnavailable(RuntimeError):
    """Raised when Ollama endpoint is unreachable."""


class OllamaBadResponse(RuntimeError):
    """Raised when Ollama response is malformed."""
