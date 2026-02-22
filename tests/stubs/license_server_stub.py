#!/usr/bin/env python3
from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


@dataclass
class StubConfig:
    valid: bool = True
    tier: str = "pro"
    valid_until: str = "2099-01-01"
    reason: str = "ok"
    status_code: int = 200


class _Handler(BaseHTTPRequestHandler):
    server_version = "LicenseStub/1.0"

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        # Silence noisy output in tests/CI.
        return

    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            parsed = json.loads(raw.decode("utf-8"))
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/healthz":
            self._send(200, {"ok": True})
            return
        self._send(404, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path.rstrip("/") != "/api/v1/validate":
            self._send(404, {"error": "not_found"})
            return

        _ = self._read_json()
        cfg: StubConfig = self.server.cfg  # type: ignore[attr-defined]
        payload = {
            "valid": bool(cfg.valid),
            "tier": cfg.tier if cfg.valid else "",
            "valid_until": cfg.valid_until if cfg.valid else "",
            "reason": cfg.reason,
        }
        self._send(int(cfg.status_code), payload)


class LicenseServerStub:
    def __init__(self, cfg: StubConfig | None = None) -> None:
        self.cfg = cfg or StubConfig()
        self.httpd: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None
        self.base_url: str | None = None

    def start(self) -> str:
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self.httpd.cfg = self.cfg  # type: ignore[attr-defined]
        host, port = self.httpd.server_address
        self.base_url = f"http://{host}:{port}"
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        return self.base_url

    def stop(self) -> None:
        if self.httpd is not None:
            self.httpd.shutdown()
            self.httpd.server_close()
        if self.thread is not None:
            self.thread.join(timeout=2)
