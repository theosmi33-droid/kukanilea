from __future__ import annotations

import hashlib

from flask import Flask

from app.security_ua_hash import sanitize_user_agent, ua_hmac_sha256_hex


def test_ua_hmac_deterministic_and_keyed() -> None:
    app = Flask(__name__)
    app.config["ANONYMIZATION_KEY"] = "test-key"

    with app.app_context():
        h1 = ua_hmac_sha256_hex("UA/1.0")
        h2 = ua_hmac_sha256_hex("UA/1.0")

    assert h1 is not None
    assert h1 == h2
    assert len(h1) == 64
    assert h1 != hashlib.sha256(b"UA/1.0").hexdigest()


def test_ua_hmac_changes_with_other_key() -> None:
    app1 = Flask(__name__)
    app1.config["ANONYMIZATION_KEY"] = "key-a"
    app2 = Flask(__name__)
    app2.config["ANONYMIZATION_KEY"] = "key-b"

    with app1.app_context():
        h1 = ua_hmac_sha256_hex("UA/1.0")
    with app2.app_context():
        h2 = ua_hmac_sha256_hex("UA/1.0")

    assert h1 is not None and h2 is not None
    assert h1 != h2


def test_sanitize_user_agent_removes_controls_and_limits_length() -> None:
    dirty = "abc\r\n\t\x00" + ("x" * 500)
    clean = sanitize_user_agent(dirty)

    assert "\r" not in clean
    assert "\n" not in clean
    assert "\t" not in clean
    assert "\x00" not in clean
    assert len(clean) <= 300


def test_hmac_returns_none_when_no_key() -> None:
    app = Flask(__name__)
    app.config["ANONYMIZATION_KEY"] = ""
    app.config["SECRET_KEY"] = ""

    with app.app_context():
        assert ua_hmac_sha256_hex("UA/1.0") is None
