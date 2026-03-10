from __future__ import annotations

from flask import Flask

from app.rate_limit import RateLimiter


def test_debug_stress_env_does_not_bypass_rate_limit(monkeypatch):
    monkeypatch.setenv("KUKANILEA_DEBUG_STRESS", "1")

    limiter = RateLimiter(limit=1, window_s=60)
    app = Flask(__name__)
    app.config["TESTING"] = False

    @app.get("/limited")
    @limiter.limit_required
    def limited():
        return "ok"

    client = app.test_client()
    first = client.get("/limited")
    second = client.get("/limited")

    assert first.status_code == 200
    assert second.status_code == 429
