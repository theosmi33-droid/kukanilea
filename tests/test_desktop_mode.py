from __future__ import annotations

import pytest

from app import desktop


class _DummyWebview:
    def __init__(self) -> None:
        self.created = []
        self.started = False

    def create_window(self, title: str, url: str, **kwargs):  # noqa: ANN003
        self.created.append((title, url, kwargs))
        return object()

    def start(self, debug: bool = False):
        self.started = True


class _DummyServer:
    def __init__(self) -> None:
        self.shutdown_called = False

    def shutdown(self) -> None:
        self.shutdown_called = True


class _DummyThread:
    def join(self, timeout: int | None = None) -> None:  # noqa: ARG002
        return None


def test_find_free_port_returns_positive_int() -> None:
    port = desktop._find_free_port()  # noqa: SLF001
    assert isinstance(port, int)
    assert port > 0


def test_run_native_desktop_bootstrap_flow(monkeypatch) -> None:
    dummy_webview = _DummyWebview()
    dummy_server = _DummyServer()
    dummy_handle = desktop._ServerHandle(  # noqa: SLF001
        server=dummy_server,
        thread=_DummyThread(),
        port=5123,
    )

    monkeypatch.setattr(desktop, "_load_webview_module", lambda: dummy_webview)
    monkeypatch.setattr(desktop, "_start_http_server", lambda port: dummy_handle)
    monkeypatch.setattr(desktop, "_wait_until_ready", lambda url: True)

    rc = desktop.run_native_desktop(title="KUKANILEA Test", debug=False)

    assert rc == 0
    assert dummy_webview.started is True
    assert dummy_server.shutdown_called is True
    assert dummy_webview.created
    _, url, _ = dummy_webview.created[0]
    assert url.startswith("http://127.0.0.1:")


def test_run_native_desktop_raises_when_not_ready(monkeypatch) -> None:
    dummy_webview = _DummyWebview()
    dummy_server = _DummyServer()
    dummy_handle = desktop._ServerHandle(  # noqa: SLF001
        server=dummy_server,
        thread=_DummyThread(),
        port=5124,
    )

    monkeypatch.setattr(desktop, "_load_webview_module", lambda: dummy_webview)
    monkeypatch.setattr(desktop, "_start_http_server", lambda port: dummy_handle)
    monkeypatch.setattr(desktop, "_wait_until_ready", lambda url: False)

    with pytest.raises(desktop.DesktopLaunchError):
        desktop.run_native_desktop(debug=False)

    assert dummy_server.shutdown_called is True
