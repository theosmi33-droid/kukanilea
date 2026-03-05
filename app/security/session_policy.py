from __future__ import annotations

from typing import Any


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def resolve_session_cookie_policy(explicit_env: str, configured_secure: Any) -> dict[str, Any]:
    env = (explicit_env or "").strip().lower()
    is_prod = env in {"prod", "production", "stage", "staging"}
    is_test = env in {"test", "testing"}
    is_dev = env in {"dev", "development", "local"}

    secure_configured = _to_bool(configured_secure)
    secure = True if is_prod else secure_configured

    if not (is_prod or is_test or is_dev):
        # Unknown env defaults to production-safe cookie posture.
        secure = True

    cookie_name = "__Host-kukanilea_session" if secure else "kukanilea_session"
    return {
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "SESSION_COOKIE_SECURE": secure,
        "SESSION_COOKIE_NAME": cookie_name,
        "SESSION_COOKIE_DOMAIN": None,
        "SESSION_COOKIE_PATH": "/",
        "SESSION_COOKIE_PARTITIONED": False,
    }
