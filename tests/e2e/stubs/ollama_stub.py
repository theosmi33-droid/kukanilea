#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class OllamaStubHandler(BaseHTTPRequestHandler):
    server_version = "OllamaStub/1.0"

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        # Silence request logs in CI output.
        return

    def _read_json(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        payload = self.rfile.read(length) if length > 0 else b"{}"
        try:
            data = json.loads(payload.decode("utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _send_json(self, status: int, body: dict) -> None:
        encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/healthz":
            self._send_json(200, {"ok": True})
            return
        if self.path == "/api/tags":
            self._send_json(
                200,
                {
                    "models": [
                        {
                            "name": "llama3.1:8b",
                            "modified_at": _now_iso(),
                            "size": 0,
                        }
                    ]
                },
            )
            return
        self._send_json(404, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        payload = self._read_json()
        model = str(payload.get("model") or "llama3.1:8b")

        if self.path in {"/api/chat", "/api/generate"}:
            message = {
                "role": "assistant",
                "content": "Stubbed Ollama response.",
            }
            self._send_json(
                200,
                {
                    "model": model,
                    "created_at": _now_iso(),
                    "message": message,
                    "response": message["content"],
                    "done": True,
                },
            )
            return
        self._send_json(404, {"error": "not_found"})


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Local stdlib Ollama API stub for E2E."
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=11435)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, int(args.port)), OllamaStubHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
