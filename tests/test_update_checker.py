from __future__ import annotations

import io
import json
import urllib.error

import app.update_checker as update_checker


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_is_newer_version_handles_beta_and_stable() -> None:
    assert update_checker.is_newer_version("1.0.0", "1.0.0-beta.1") is True
    assert update_checker.is_newer_version("1.0.0-beta.2", "1.0.0-beta.1") is True
    assert update_checker.is_newer_version("1.0.0-beta.1", "1.0.0") is False


def test_check_for_updates_success(monkeypatch) -> None:
    def _fake_urlopen(req, timeout=5):  # noqa: ANN001
        return _FakeResponse(
            {
                "tag_name": "v1.0.0-beta.2",
                "html_url": "https://github.com/theosmi33-droid/kukanilea/releases/tag/v1.0.0-beta.2",
            }
        )

    monkeypatch.setattr(update_checker.urllib.request, "urlopen", _fake_urlopen)

    result = update_checker.check_for_updates("1.0.0-beta.1")
    assert result["checked"] is True
    assert result["update_available"] is True
    assert result["latest_version"] == "1.0.0-beta.2"
    assert result["download_url"].startswith("https://")


def test_check_for_updates_handles_http_error(monkeypatch) -> None:
    def _fake_urlopen(req, timeout=5):  # noqa: ANN001
        raise urllib.error.HTTPError(
            req.full_url,
            503,
            "Service unavailable",
            hdrs=None,
            fp=io.BytesIO(b"{}"),
        )

    monkeypatch.setattr(update_checker.urllib.request, "urlopen", _fake_urlopen)

    result = update_checker.check_for_updates("1.0.0-beta.1")
    assert result["checked"] is False
    assert result["error"] == "http_503"
