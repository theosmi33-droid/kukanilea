from __future__ import annotations

import time
from typing import Any, Callable, Tuple


class Metrics:
    """
    Performance measurement utility.
    """

    def measure(self, fn: Callable, *args, **kwargs) -> Tuple[Any, float]:
        start = time.time()
        result = fn(*args, **kwargs)
        duration = time.time() - start
        return result, duration
