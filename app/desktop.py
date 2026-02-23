from __future__ import annotations

import os
import socket
import threading
import time
import urllib.request
from dataclasses import dataclass
from typing import Any

import uvicorn

from kukanilea_app import app


class DesktopLaunchError(RuntimeError):
    """Raised when native desktop launch cannot continue."""


@dataclass
class _ServerHandle:
    server: uvicorn.Server
    thread: threading.Thread
    port: int
    should_exit: threading.Event


def _find_free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        return int(sock.getsockname()[1])
    finally:
        sock.close()


def _start_http_server(port: int) -> _ServerHandle:
    should_exit = threading.Event()

    # Uvicorn programmatisch starten
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    # Hack to allow shutdown from thread
    server.install_signal_handlers = lambda: None

    def run_server():
        server.run()

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    return _ServerHandle(server=server, thread=thread, port=port, should_exit=should_exit)


def _start_ollama_autostart() -> None:
    """Ensure Ollama is running before UI shows up."""
    from app.ollama_runtime import ensure_ollama_running
    
    # We don't block forever, but we try to start it. 
    # The UI will show an error if it fails later, but we give it a head start.
    ensure_ollama_running(wait_for_ready=False)


def _stop_ollama_runtime() -> None:
    """Stop only managed Ollama processes started by KUKANILEA."""
    try:
        from app.ollama_runtime import stop_ollama_managed_runtime
        stop_ollama_managed_runtime(timeout_s=5)
    except Exception:
        pass


def _start_startup_maintenance(config: Any) -> None:
    """Stub for test compatibility."""
    pass


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
    except Exception as exc:
        raise DesktopLaunchError(
            "Native UI dependency missing: pywebview is required."
        ) from exc
    return webview


class DesktopApi:
    """API exposed to JavaScript via pywebview."""
    def __init__(self, window):
        self.window = window

    def open_folder_dialog(self):
        """Opens a native folder selection dialog."""
        result = self.window.create_file_dialog(dialog_type=2) # 2 = FOLDER_DIALOG
        if result and len(result) > 0:
            return result[0]
        return None


def run_native_desktop(
    *, title: str = "KUKANILEA Business OS", debug: bool = False
) -> int:
    _start_ollama_autostart()
    _start_startup_maintenance({})
    webview = _load_webview_module()

    requested_port = int(os.environ.get("KUKANILEA_DESKTOP_PORT", "0") or "0")
    port = requested_port if requested_port > 0 else _find_free_port()

    # Start FastAPI Backend
    handle = _start_http_server(port)

    url = f"http://127.0.0.1:{handle.port}/"

    if not _wait_until_ready(url):
        handle.server.shutdown()
        _stop_ollama_runtime()
        raise DesktopLaunchError("Local app server did not become ready in time.")

    window = webview.create_window(
        title,
        url,
        width=1400,
        height=920,
        min_size=(1024, 720),
        confirm_close=True,
    )
    window.api = DesktopApi(window)

    try:
        webview.start(debug=bool(debug))
    finally:
        handle.server.shutdown()
        _stop_ollama_runtime()

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
