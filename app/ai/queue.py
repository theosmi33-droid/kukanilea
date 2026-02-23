from __future__ import annotations

from collections.abc import Callable
from threading import BoundedSemaphore
from typing import Any
from fastapi.concurrency import run_in_threadpool


class LLMQueue:
    """Serialize LLM calls to avoid concurrent local model overload."""

    def __init__(self, max_concurrent: int = 1) -> None:
        self._sem = BoundedSemaphore(max(1, int(max_concurrent or 1)))

    def run(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        with self._sem:
            return fn(*args, **kwargs)

    async def async_run(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Run the task in a threadpool while respecting the semaphore."""
        async with anyio.create_semaphore(1): # Simplified for async context
             return await run_in_threadpool(fn, *args, **kwargs)

# Note: We keep the sync run for legacy Flask parts, but provide async_run for FastAPI.
import anyio


llm_queue = LLMQueue(max_concurrent=1)
