"""
app/core/cache.py
In-memory caching layer.
"""
import time
import threading
from typing import Any, Optional, Dict

class SimpleCache:
    def __init__(self, default_ttl: int = 300):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self.default_ttl = default_ttl

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            item = self._cache.get(key)
            if item:
                if time.time() > item["expires_at"]:
                    del self._cache[key]
                    return None
                return item["value"]
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        ttl = ttl if ttl is not None else self.default_ttl
        with self._lock:
            self._cache[key] = {
                "value": value,
                "expires_at": time.time() + ttl
            }

    def delete(self, key: str):
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                
    def clear(self):
        with self._lock:
            self._cache.clear()

# Global Instance
cache = SimpleCache()
