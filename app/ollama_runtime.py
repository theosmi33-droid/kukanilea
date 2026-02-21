from __future__ import annotations

import logging
import os
import platform
import shutil
import subprocess
import threading
import time

import requests

LOG = logging.getLogger(__name__)
_TRUTHY = {"1", "true", "yes", "on"}


def _env_bool(name: str, default: str = "0") -> bool:
    return str(os.environ.get(name, default)).strip().lower() in _TRUTHY


def _base_url() -> str:
    return (
        str(
            os.environ.get("OLLAMA_BASE_URL") or os.environ.get("OLLAMA_HOST") or ""
        ).strip()
        or "http://127.0.0.1:11434"
    )


def _autostart_enabled() -> bool:
    return _env_bool("KUKANILEA_OLLAMA_AUTOSTART", "1")


def _autostart_timeout_seconds() -> int:
    raw = str(os.environ.get("KUKANILEA_OLLAMA_AUTOSTART_TIMEOUT_SECONDS", "20"))
    try:
        return max(1, int(raw))
    except Exception:
        return 20


def _is_ollama_ready(timeout_s: int = 2) -> bool:
    try:
        res = requests.get(f"{_base_url().rstrip('/')}/api/tags", timeout=timeout_s)
        return res.status_code == 200
    except Exception:
        return False


def _launch_macos_ollama_app() -> bool:
    if platform.system().lower() != "darwin":
        return False
    cmd = ["open", "-g", "-a", "Ollama"]
    try:
        res = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return res.returncode == 0
    except Exception:
        return False


def _launch_ollama_serve() -> bool:
    ollama_bin = shutil.which("ollama")
    if not ollama_bin:
        return False
    try:
        subprocess.Popen(  # noqa: S603
            [ollama_bin, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
        return True
    except Exception:
        return False


def _wait_until_ready(timeout_s: int) -> bool:
    deadline = time.monotonic() + max(1, int(timeout_s))
    while time.monotonic() < deadline:
        if _is_ollama_ready(timeout_s=2):
            return True
        time.sleep(0.5)
    return _is_ollama_ready(timeout_s=2)


def ensure_ollama_running(
    *, wait_for_ready: bool = True, timeout_s: int | None = None
) -> bool:
    """Ensure a local Ollama service is up, optionally waiting until ready."""
    if _is_ollama_ready(timeout_s=2):
        return True

    if not _autostart_enabled():
        return False

    launched = _launch_macos_ollama_app()
    if not launched:
        launched = _launch_ollama_serve()

    if not launched:
        LOG.warning("Ollama autostart failed: no launch strategy available.")
        return False

    if not wait_for_ready:
        return _is_ollama_ready(timeout_s=2)

    timeout = _autostart_timeout_seconds() if timeout_s is None else int(timeout_s)
    ok = _wait_until_ready(timeout)
    if not ok:
        LOG.warning("Ollama autostart timed out after %ss.", timeout)
    return ok


def start_ollama_autostart_background() -> threading.Thread | None:
    """Kick off Ollama autostart without blocking UI startup."""
    if _is_ollama_ready(timeout_s=2):
        return None
    if not _autostart_enabled():
        return None

    thread = threading.Thread(
        target=ensure_ollama_running,
        kwargs={"wait_for_ready": True},
        name="kukanilea-ollama-autostart",
        daemon=True,
    )
    thread.start()
    return thread
