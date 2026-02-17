from __future__ import annotations

import base64
import hashlib
from urllib.parse import parse_qs, urlparse

import pytest

from app.mail.postfach_oauth import (
    build_authorization_url,
    generate_pkce_pair,
    normalize_token_payload,
    provider_config,
    xoauth2_auth_string,
)


def test_generate_pkce_pair_is_sha256_urlsafe() -> None:
    verifier, challenge = generate_pkce_pair()
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    assert challenge == expected
    assert len(verifier) >= 43
    assert len(challenge) >= 43


def test_build_authorization_url_contains_pkce_and_state() -> None:
    cfg = provider_config("google")
    url = build_authorization_url(
        provider="google",
        client_id="client-id-123",
        redirect_uri="http://127.0.0.1:5051/postfach/accounts/oauth/callback",
        state="abc-state",
        code_challenge="pkce-challenge",
        login_hint="user@example.com",
    )
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    assert url.startswith(str(cfg["auth_url"]))
    assert query["client_id"] == ["client-id-123"]
    assert query["state"] == ["abc-state"]
    assert query["code_challenge"] == ["pkce-challenge"]
    assert query["code_challenge_method"] == ["S256"]
    assert query["response_type"] == ["code"]
    assert query["login_hint"] == ["user@example.com"]


def test_normalize_token_payload_requires_access_token() -> None:
    with pytest.raises(ValueError, match="oauth_access_token_missing"):
        normalize_token_payload({"token_type": "Bearer"})


def test_xoauth2_auth_string_contains_user_and_bearer_token() -> None:
    encoded = xoauth2_auth_string("sender@example.com", "token-abc")
    raw = base64.b64decode(encoded).decode("utf-8")
    assert "user=sender@example.com" in raw
    assert "auth=Bearer token-abc" in raw
