from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Mapping


def canonical_hash(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class IdempotencyDecision:
    status: str
    token: str | None = None
    response: dict[str, Any] | None = None
    status_code: int | None = None


@dataclass
class _Entry:
    request_hash: str
    created_at: float
    expires_at: float
    status: str
    token: str
    response: dict[str, Any] | None = None
    status_code: int | None = None


class IdempotencyStore:
    def __init__(self, *, max_entries: int = 1024, max_response_bytes: int = 64 * 1024) -> None:
        self._lock = threading.Lock()
        self._entries: dict[str, _Entry] = {}
        self._counter = 0
        self._max_entries = max(1, int(max_entries))
        self._max_response_bytes = max(512, int(max_response_bytes))

    def _next_token(self) -> str:
        self._counter += 1
        return f"idem-{self._counter:08d}"

    def _prune(self, now: float) -> None:
        expired = [key for key, entry in self._entries.items() if entry.expires_at <= now]
        for key in expired:
            self._entries.pop(key, None)

    def _evict_one_for_capacity(self) -> None:
        if not self._entries:
            return
        completed = [(key, entry) for key, entry in self._entries.items() if entry.status == "completed"]
        candidates = completed or list(self._entries.items())
        victim_key, _ = min(candidates, key=lambda item: (item[1].expires_at, item[1].created_at))
        self._entries.pop(victim_key, None)

    def _bounded_response(self, response: Mapping[str, Any]) -> dict[str, Any]:
        copy = dict(response)
        serialized = json.dumps(copy, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        if len(serialized.encode("utf-8")) <= self._max_response_bytes:
            return copy
        return {
            "ok": bool(copy.get("ok", True)),
            "tool": copy.get("tool"),
            "name": copy.get("name"),
            "result": {"truncated": True},
        }

    def begin(self, *, scope: str, key: str, request_hash: str, ttl_seconds: int) -> IdempotencyDecision:
        now = time.time()
        scoped_key = f"{scope}:{key}"
        with self._lock:
            self._prune(now)
            existing = self._entries.get(scoped_key)
            if existing is not None:
                if existing.request_hash != request_hash:
                    return IdempotencyDecision(status="conflict")
                if existing.status == "in_flight":
                    return IdempotencyDecision(status="in_flight")
                return IdempotencyDecision(
                    status="replay",
                    response=dict(existing.response or {}),
                    status_code=int(existing.status_code or 200),
                )

            token = self._next_token()
            while len(self._entries) >= self._max_entries:
                self._evict_one_for_capacity()
            self._entries[scoped_key] = _Entry(
                request_hash=request_hash,
                created_at=now,
                expires_at=now + max(1, int(ttl_seconds)),
                status="in_flight",
                token=token,
            )
            return IdempotencyDecision(status="proceed", token=token)

    def complete_success(
        self,
        *,
        scope: str,
        key: str,
        token: str,
        response: Mapping[str, Any],
        status_code: int,
        ttl_seconds: int,
    ) -> None:
        now = time.time()
        scoped_key = f"{scope}:{key}"
        with self._lock:
            entry = self._entries.get(scoped_key)
            if entry is None or entry.token != token:
                return
            entry.status = "completed"
            entry.response = self._bounded_response(response)
            entry.status_code = int(status_code)
            entry.expires_at = now + max(1, int(ttl_seconds))

    def complete_failure(self, *, scope: str, key: str, token: str) -> None:
        scoped_key = f"{scope}:{key}"
        with self._lock:
            entry = self._entries.get(scoped_key)
            if entry is None or entry.token != token:
                return
            self._entries.pop(scoped_key, None)


GLOBAL_IDEMPOTENCY_STORE = IdempotencyStore()
