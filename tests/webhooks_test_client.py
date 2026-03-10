from __future__ import annotations

import socket
import urllib.error

from app.webhooks import client


def test_validate_webhook_url_rejects_private_dns_resolution(monkeypatch):
    monkeypatch.setattr(client.Config, "WEBHOOK_ALLOWED_DOMAINS", "example.com", raising=False)

    def fake_getaddrinfo(host, port):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0))]

    monkeypatch.setattr(client.socket, "getaddrinfo", fake_getaddrinfo)

    assert client._validate_webhook_url("https://example.com/hook") is None


def test_execute_webhook_action_does_not_follow_redirects(monkeypatch):
    monkeypatch.setattr(client.Config, "WEBHOOK_ALLOWED_DOMAINS", "example.com", raising=False)

    def fake_getaddrinfo(host, port):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]

    monkeypatch.setattr(client.socket, "getaddrinfo", fake_getaddrinfo)

    class FakeOpener:
        def open(self, req, timeout):
            raise urllib.error.HTTPError(
                url=req.full_url,
                code=302,
                msg="Found",
                hdrs=None,
                fp=None,
            )

    monkeypatch.setattr(client.urllib.request, "build_opener", lambda *_: FakeOpener())

    result = client.execute_webhook_action(
        action_cfg={"method": "POST", "url": "https://example.com/hook"},
        context={},
    )

    assert result == {"status": "failed", "error": "webhook_http_302"}
