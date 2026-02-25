from __future__ import annotations

import hashlib
import hmac
import os

from flask import current_app, has_app_context


def sanitize_user_agent(ua: str) -> str:
    value = str(ua or "")
    value = (
        value.replace("\r", " ")
        .replace("\n", " ")
        .replace("\0", " ")
        .replace("\t", " ")
    )
    value = "".join(ch if ord(ch) >= 0x20 else " " for ch in value)
    value = " ".join(value.split()).strip()
    if len(value) > 300:
        value = value[:300]
    return value


def get_ua_hmac_key() -> bytes | None:
    try:
        if has_app_context():
            cfg_key = current_app.config.get("ANONYMIZATION_KEY")
            if cfg_key:
                if isinstance(cfg_key, bytes):
                    return cfg_key if cfg_key else None
                return str(cfg_key).encode("utf-8")

        env_key = os.environ.get("KUKANILEA_ANONYMIZATION_KEY")
        if env_key:
            return env_key.encode("utf-8")

        if has_app_context():
            fallback = current_app.config.get("SECRET_KEY")
            if fallback:
                if isinstance(fallback, bytes):
                    return fallback if fallback else None
                return str(fallback).encode("utf-8")
    except Exception:
        return None

    return None


def ua_hmac_sha256_hex(ua: str) -> str | None:
    try:
        key = get_ua_hmac_key()
        if not key:
            return None
        ua_s = sanitize_user_agent(ua)
        return hmac.new(key, ua_s.encode("utf-8"), hashlib.sha256).hexdigest()
    except Exception:
        return None
