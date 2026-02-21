from __future__ import annotations

import logging
import os
import platform
import shutil
import subprocess as sp
import threading
import time
from pathlib import Path

import requests

LOG = logging.getLogger(__name__)
_TRUTHY = {"1", "true", "yes", "on"}
_RUNTIME_LOCK = threading.Lock()
_MANAGED_SERVE_PROCESS: sp.Popen | None = None
_MANAGED_APP_LAUNCHED = False


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


def _stop_on_exit_enabled() -> bool:
    return _env_bool("KUKANILEA_OLLAMA_STOP_ON_EXIT", "1")


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
        res = sp.run(
            cmd,
            stdout=sp.DEVNULL,
            stderr=sp.DEVNULL,
            shell=False,
            timeout=5,
            check=False,
        )
        return res.returncode == 0
    except Exception:
        return False


def _launch_ollama_serve() -> bool:
    global _MANAGED_SERVE_PROCESS
    ollama_bin = _find_ollama_binary()
    if not ollama_bin:
        return False
    with _RUNTIME_LOCK:
        if _MANAGED_SERVE_PROCESS is not None and _MANAGED_SERVE_PROCESS.poll() is None:
            return True
    try:
        proc = sp.Popen(  # noqa: S603
            [ollama_bin, "serve"],
            stdout=sp.DEVNULL,
            stderr=sp.DEVNULL,
            stdin=sp.DEVNULL,
            shell=False,
            start_new_session=True,
        )
    except Exception:
        return False
    with _RUNTIME_LOCK:
        _MANAGED_SERVE_PROCESS = proc
        return True


def _find_ollama_binary() -> str:
    found = shutil.which("ollama")
    if found:
        return found
    candidates = (
        "/opt/homebrew/opt/ollama/bin/ollama",
        "/usr/local/opt/ollama/bin/ollama",
        "/Applications/Ollama.app/Contents/Resources/ollama",
    )
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    return ""


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

    # Prefer managed `ollama serve` so we can tear it down when KUKANILEA exits.
    launched = _launch_ollama_serve()
    if not launched:
        launched = _launch_macos_ollama_app()
        if launched:
            global _MANAGED_APP_LAUNCHED
            with _RUNTIME_LOCK:
                _MANAGED_APP_LAUNCHED = True

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


def stop_ollama_managed_runtime(*, timeout_s: int = 8) -> bool:
    """Stop only Ollama processes started by this runtime."""
    global _MANAGED_SERVE_PROCESS, _MANAGED_APP_LAUNCHED
    stopped = False
    if not _stop_on_exit_enabled():
        return False

    proc: sp.Popen | None
    with _RUNTIME_LOCK:
        proc = _MANAGED_SERVE_PROCESS
        _MANAGED_SERVE_PROCESS = None
    if proc is not None:
        try:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=max(1, int(timeout_s)))
                except Exception:
                    proc.kill()
                    proc.wait(timeout=2)
                stopped = True
        except Exception:
            LOG.debug("Failed to stop managed Ollama serve process.", exc_info=True)

    launched_app = False
    with _RUNTIME_LOCK:
        launched_app = bool(_MANAGED_APP_LAUNCHED)
        _MANAGED_APP_LAUNCHED = False
    if launched_app and platform.system().lower() == "darwin":
        try:
            res = sp.run(
                ["osascript", "-e", 'tell application "Ollama" to quit'],
                stdout=sp.DEVNULL,
                stderr=sp.DEVNULL,
                check=False,
                shell=False,
                timeout=5,
            )
            if res.returncode == 0:
                stopped = True
        except Exception:
            LOG.debug("Failed to request Ollama.app shutdown.", exc_info=True)
    return stopped


def pull_ollama_model(*, model: str, timeout_s: int = 1800) -> bool:
    """Pull one model into local Ollama cache. Best-effort, returns success bool."""
    model_name = str(model or "").strip()
    if not model_name:
        return False
    ollama_bin = _find_ollama_binary()
    if not ollama_bin:
        return False

    env = os.environ.copy()
    env["OLLAMA_HOST"] = _base_url()
    try:
        res = sp.run(  # noqa: S603
            [ollama_bin, "pull", model_name],
            stdout=sp.DEVNULL,
            stderr=sp.DEVNULL,
            shell=False,
            timeout=max(30, int(timeout_s)),
            check=False,
            env=env,
        )
        return res.returncode == 0
    except Exception:
        return False
