from __future__ import annotations

import subprocess

from app import ollama_runtime as rt


def test_ensure_ollama_running_returns_true_when_already_up(monkeypatch) -> None:
    monkeypatch.setattr(rt, "_is_ollama_ready", lambda timeout_s=2: True)
    monkeypatch.setattr(rt, "_launch_macos_ollama_app", lambda: False)
    monkeypatch.setattr(rt, "_launch_ollama_serve", lambda: False)
    assert rt.ensure_ollama_running(wait_for_ready=True) is True


def test_ensure_ollama_running_respects_disabled_autostart(monkeypatch) -> None:
    monkeypatch.setenv("KUKANILEA_OLLAMA_AUTOSTART", "0")
    monkeypatch.setattr(rt, "_is_ollama_ready", lambda timeout_s=2: False)
    called = {"app": 0, "serve": 0}
    monkeypatch.setattr(
        rt, "_launch_macos_ollama_app", lambda: called.__setitem__("app", 1) or True
    )
    monkeypatch.setattr(
        rt, "_launch_ollama_serve", lambda: called.__setitem__("serve", 1) or True
    )
    assert rt.ensure_ollama_running(wait_for_ready=False) is False
    assert called == {"app": 0, "serve": 0}


def test_ensure_ollama_running_launches_and_waits(monkeypatch) -> None:
    monkeypatch.setenv("KUKANILEA_OLLAMA_AUTOSTART", "1")
    seq = iter([False, False, True])
    monkeypatch.setattr(rt, "_is_ollama_ready", lambda timeout_s=2: next(seq, True))
    monkeypatch.setattr(rt, "_launch_macos_ollama_app", lambda: True)
    monkeypatch.setattr(rt, "_launch_ollama_serve", lambda: False)
    monkeypatch.setattr(rt.time, "sleep", lambda *_: None)
    assert rt.ensure_ollama_running(wait_for_ready=True, timeout_s=2) is True


def test_ensure_ollama_running_falls_back_to_serve(monkeypatch) -> None:
    monkeypatch.setenv("KUKANILEA_OLLAMA_AUTOSTART", "1")
    seq = iter([False, False, True])
    monkeypatch.setattr(rt, "_is_ollama_ready", lambda timeout_s=2: next(seq, True))
    monkeypatch.setattr(rt, "_launch_macos_ollama_app", lambda: False)
    monkeypatch.setattr(rt, "_launch_ollama_serve", lambda: True)
    monkeypatch.setattr(rt.time, "sleep", lambda *_: None)
    assert rt.ensure_ollama_running(wait_for_ready=True, timeout_s=2) is True


def test_find_ollama_binary_checks_common_paths(monkeypatch) -> None:
    candidate = "/opt/homebrew/opt/ollama/bin/ollama"
    monkeypatch.setattr(rt.shutil, "which", lambda *_: None)
    monkeypatch.setattr(
        rt.Path,
        "exists",
        lambda p: str(p) == candidate,
    )
    assert rt._find_ollama_binary() == candidate  # noqa: SLF001


def test_stop_ollama_managed_runtime_terminates_managed_process(monkeypatch) -> None:
    class _Proc:
        def __init__(self) -> None:
            self._alive = True
            self.terminated = False
            self.killed = False

        def poll(self):
            return None if self._alive else 0

        def terminate(self) -> None:
            self.terminated = True
            self._alive = False

        def wait(self, timeout=None):  # noqa: ANN001, ARG002
            return 0

        def kill(self) -> None:
            self.killed = True
            self._alive = False

    proc = _Proc()
    monkeypatch.setenv("KUKANILEA_OLLAMA_STOP_ON_EXIT", "1")
    monkeypatch.setattr(rt, "_MANAGED_SERVE_PROCESS", proc)
    monkeypatch.setattr(rt, "_MANAGED_APP_LAUNCHED", False)

    assert rt.stop_ollama_managed_runtime(timeout_s=1) is True
    assert proc.terminated is True
    assert proc.killed is False
    assert rt._MANAGED_SERVE_PROCESS is None  # noqa: SLF001


def test_stop_ollama_managed_runtime_can_quit_launched_app(monkeypatch) -> None:
    monkeypatch.setenv("KUKANILEA_OLLAMA_STOP_ON_EXIT", "1")
    monkeypatch.setattr(rt.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(rt, "_MANAGED_SERVE_PROCESS", None)
    monkeypatch.setattr(rt, "_MANAGED_APP_LAUNCHED", True)
    monkeypatch.setattr(
        rt.sp,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args=args, returncode=0),
    )
    assert rt.stop_ollama_managed_runtime(timeout_s=1) is True
