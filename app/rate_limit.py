from __future__ import annotations

import functools
import time
from dataclasses import dataclass, field
from typing import Dict, Tuple

from flask import abort, request


@dataclass
class RateLimiter:
    limit: int
    window_s: int
    hits: Dict[str, Tuple[int, float]] = field(default_factory=dict)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        count, window_start = self.hits.get(key, (0, now))
        if now - window_start > self.window_s:
            self.hits[key] = (1, now)
            return True
        if count >= self.limit:
            return False
        self.hits[key] = (count + 1, window_start)
        return True

    def limit_required(self, fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            key = request.remote_addr or "unknown"
            if not self.allow(key):
                abort(429, description="Too many requests. Please try again later.")
            return fn(*args, **kwargs)

        return wrapper


chat_limiter = RateLimiter(limit=30, window_s=60)
search_limiter = RateLimiter(limit=60, window_s=60)
upload_limiter = RateLimiter(limit=20, window_s=60)
