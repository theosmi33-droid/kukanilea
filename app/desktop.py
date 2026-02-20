from __future__ import annotations

import os
import socket
import threading
import time
import urllib.request
from dataclasses import dataclass
from typing import Any

from werkzeug.serving import make_server

from . import create_app


class DesktopLaunchError(RuntimeError):
    """Raised when native desktop launch cannot continue."""


@dataclass
class _ServerHandle:
    server: Any
    thread: threading.Thread
    port: int


def _find_free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        return int(sock.getsockname()[1])
    finally:
        sock.close()


def _start_http_server(port: int) -> _ServerHandle:
    app = create_app()
    server = make_server("127.0.0.1", int(port), app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return _ServerHandle(server=server, thread=thread, port=int(server.server_port))


def _wait_until_ready(url: str, timeout_seconds: int = 20) -> bool:
    deadline = time.time() + max(1, int(timeout_seconds))
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1):
                return True
        except Exception:
            time.sleep(0.2)
    return False


def _load_webview_module() -> Any:
    try:
        import webview
    except Exception as exc:  # pragma: no cover - exercised via runtime env
        raise DesktopLaunchError(
            "Native UI dependency missing: pywebview is required."
        ) from exc
    return webview


def run_native_desktop(*, title: str = "KUKANILEA", debug: bool = False) -> int:
    webview = _load_webview_module()

    requested_port = int(os.environ.get("KUKANILEA_DESKTOP_PORT", "0") or "0")
    port = requested_port if requested_port > 0 else _find_free_port()

    handle = _start_http_server(port)
    url = f"http://127.0.0.1:{handle.port}/"

    if not _wait_until_ready(url):
        try:
            handle.server.shutdown()
        finally:
            handle.thread.join(timeout=3)
        raise DesktopLaunchError("Local app server did not become ready in time.")

    webview.create_window(
        title,
        url,
        width=1400,
        height=920,
        min_size=(1024, 720),
        confirm_close=True,
    )

    try:
        webview.start(debug=bool(debug))
    finally:
        try:
            handle.server.shutdown()
        finally:
            handle.thread.join(timeout=3)

    return 0


def main() -> int:
    debug = str(os.environ.get("KUKANILEA_DESKTOP_DEBUG", "0")).strip() in {
        "1",
        "true",
        "TRUE",
        "yes",
        "YES",
    }
    return run_native_desktop(debug=debug)
