from __future__ import annotations

from urllib.parse import urlparse


def parse_cors_allowlist(raw: str) -> set[str]:
    origins = set()
    for item in (raw or "").split(","):
        val = item.strip().lower()
        if val:
            origins.add(val)
    return origins


def is_allowed_redirect_target(target: str, allowed_hosts: set[str]) -> bool:
    if not target:
        return False
    parsed = urlparse(target)
    if parsed.scheme or parsed.netloc:
        return parsed.netloc.lower() in {h.lower() for h in allowed_hosts}
    return target.startswith("/") and not target.startswith("//")
