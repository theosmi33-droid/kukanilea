from __future__ import annotations

from threading import BoundedSemaphore
from typing import Any, Callable


class LLMQueue:
    """Serialize LLM calls to avoid concurrent local model overload."""

    def __init__(self, max_concurrent: int = 1) -> None:
        self._sem = BoundedSemaphore(max(1, int(max_concurrent or 1)))

    def run(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        with self._sem:
            return fn(*args, **kwargs)


llm_queue = LLMQueue(max_concurrent=1)
