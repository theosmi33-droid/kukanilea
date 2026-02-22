from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request


class HttpError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def _requests_module() -> object | None:
    try:
        import requests  # type: ignore

        return requests
    except Exception:
        return None


def _mock_response(url: str) -> tuple[int, bytes] | None:
    fixture = os.environ.get("KUKANILEA_SKILLS_HTTP_MOCK")
    if not fixture:
        return None
    try:
        payload = json.loads(open(fixture, encoding="utf-8").read())
        item = payload.get(url)
        if item is None:
            return 404, b""
        status = int(item.get("status", 200))
        if "bytes_b64" in item:
            return status, base64.b64decode(item["bytes_b64"])
        text = str(item.get("text", ""))
        return status, text.encode("utf-8")
    except Exception as exc:
        raise HttpError(f"mock_fixture_failed:{exc}") from exc


def http_get_bytes(url: str, timeout: int = 20) -> bytes:
    mocked = _mock_response(url)
    if mocked is not None:
        status, data = mocked
        if status != 200:
            raise HttpError(f"http_error:{status} {url}", status)
        return data

    req_mod = _requests_module()
    if req_mod is not None:
        try:
            resp = req_mod.get(url, timeout=timeout)
            if int(resp.status_code) != 200:
                raise HttpError(
                    f"http_error:{resp.status_code} {url}", int(resp.status_code)
                )
            return bytes(resp.content)
        except HttpError:
            raise
        except Exception as exc:
            raise HttpError(f"request_failed:{url}: {exc}") from exc

    req = urllib.request.Request(
        url, headers={"User-Agent": "kukanilea-skill-import/1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status = int(getattr(response, "status", 200))
            if status != 200:
                raise HttpError(f"http_error:{status} {url}", status)
            return bytes(response.read())
    except urllib.error.HTTPError as exc:
        raise HttpError(f"http_error:{exc.code} {url}", int(exc.code)) from exc
    except urllib.error.URLError as exc:
        raise HttpError(f"request_failed:{url}: {exc}") from exc


def http_get_text(url: str, timeout: int = 20) -> str:
    raw = http_get_bytes(url, timeout=timeout)
    return raw.decode("utf-8")
