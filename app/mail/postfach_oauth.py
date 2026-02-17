from __future__ import annotations

import base64
import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib import parse, request

ProviderConfig = dict[str, Any]


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def _scopes_google() -> list[str]:
    return [
        "https://mail.google.com/",
        "openid",
        "email",
        "profile",
    ]


def _scopes_microsoft() -> list[str]:
    return [
        "offline_access",
        "IMAP.AccessAsUser.All",
        "SMTP.Send",
        "User.Read",
    ]


def provider_config(provider: str) -> ProviderConfig:
    key = (provider or "").strip().lower()
    if key in {"google", "gmail"}:
        return {
            "provider": "google",
            "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_url": "https://oauth2.googleapis.com/token",
            "scopes": _scopes_google(),
            "imap_host": "imap.gmail.com",
            "imap_port": 993,
            "smtp_host": "smtp.gmail.com",
            "smtp_port": 465,
        }
    if key in {"microsoft", "m365", "office365", "exchange"}:
        return {
            "provider": "microsoft",
            "auth_url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
            "token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
            "scopes": _scopes_microsoft(),
            "imap_host": "outlook.office365.com",
            "imap_port": 993,
            "smtp_host": "smtp.office365.com",
            "smtp_port": 587,
        }
    raise ValueError("oauth_provider_unsupported")


def generate_state() -> str:
    return secrets.token_urlsafe(32)


def generate_pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def build_authorization_url(
    *,
    provider: str,
    client_id: str,
    redirect_uri: str,
    state: str,
    code_challenge: str,
    login_hint: str | None = None,
    scopes: list[str] | None = None,
) -> str:
    cfg = provider_config(provider)
    if not str(client_id or "").strip():
        raise ValueError("oauth_client_id_missing")
    scope_list = list(scopes or cfg["scopes"])
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(scope_list),
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "access_type": "offline",
        "prompt": "consent",
    }
    if login_hint:
        params["login_hint"] = login_hint
    return f"{cfg['auth_url']}?{parse.urlencode(params)}"


def _token_request(
    token_url: str,
    data: dict[str, str],
    *,
    timeout: int = 20,
) -> dict[str, Any]:
    encoded = parse.urlencode(data).encode("utf-8")
    req = request.Request(
        token_url,
        data=encoded,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", errors="replace")
    payload = json.loads(body or "{}")
    if not isinstance(payload, dict):
        raise ValueError("oauth_token_invalid_response")
    return payload


def exchange_code_for_tokens(
    *,
    provider: str,
    client_id: str,
    code: str,
    redirect_uri: str,
    code_verifier: str,
    client_secret: str | None = None,
    timeout: int = 20,
) -> dict[str, Any]:
    cfg = provider_config(provider)
    token_payload = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "code": code,
        "redirect_uri": redirect_uri,
        "code_verifier": code_verifier,
    }
    if client_secret:
        token_payload["client_secret"] = client_secret
    payload = _token_request(cfg["token_url"], token_payload, timeout=timeout)
    return normalize_token_payload(payload)


def refresh_access_token(
    *,
    provider: str,
    client_id: str,
    refresh_token: str,
    scopes: list[str] | None = None,
    client_secret: str | None = None,
    timeout: int = 20,
) -> dict[str, Any]:
    cfg = provider_config(provider)
    token_payload = {
        "grant_type": "refresh_token",
        "client_id": client_id,
        "refresh_token": refresh_token,
    }
    if scopes:
        token_payload["scope"] = " ".join(scopes)
    if client_secret:
        token_payload["client_secret"] = client_secret
    payload = _token_request(cfg["token_url"], token_payload, timeout=timeout)
    return normalize_token_payload(payload, fallback_refresh_token=refresh_token)


def normalize_token_payload(
    payload: dict[str, Any],
    *,
    fallback_refresh_token: str | None = None,
) -> dict[str, Any]:
    access_token = str(payload.get("access_token") or "").strip()
    if not access_token:
        raise ValueError("oauth_access_token_missing")
    refresh_token = str(
        payload.get("refresh_token") or fallback_refresh_token or ""
    ).strip()
    scope_text = str(payload.get("scope") or "").strip()
    scopes = [s for s in scope_text.split() if s]
    expires_in = int(payload.get("expires_in") or 3600)
    expires_at = _iso(_now_utc() + timedelta(seconds=max(60, expires_in)))
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": str(payload.get("token_type") or "Bearer"),
        "scopes": scopes,
        "expires_at": expires_at,
    }


def xoauth2_auth_string(username: str, access_token: str) -> str:
    raw = f"user={username}\x01auth=Bearer {access_token}\x01\x01"
    return base64.b64encode(raw.encode("utf-8")).decode("ascii")
