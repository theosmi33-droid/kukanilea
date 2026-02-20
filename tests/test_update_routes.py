from __future__ import annotations

import re
from pathlib import Path

from app import create_app
from app.config import Config


def _make_app(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(Config, "AUTH_DB", tmp_path / "auth.sqlite3")
    monkeypatch.setattr(Config, "CORE_DB", tmp_path / "core.sqlite3")
    monkeypatch.setattr(Config, "UPDATE_CHECK_ENABLED", False)
    monkeypatch.setattr(Config, "UPDATE_INSTALL_ENABLED", False)
    monkeypatch.setattr(Config, "UPDATE_INSTALL_URL", "https://example.invalid/release")
    monkeypatch.setattr(Config, "UPDATE_APP_DIR", tmp_path / "KUKANILEA.app")
    monkeypatch.setattr(Config, "UPDATE_DOWNLOAD_DIR", tmp_path / "downloads")
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test", READ_ONLY=False)
    return app


def _login(client, role: str = "DEV") -> None:
    with client.session_transaction() as sess:
        sess["user"] = "dev"
        sess["role"] = role
        sess["tenant_id"] = "KUKANILEA"


def _csrf_from_html(payload: bytes) -> str:
    match = re.search(rb'name="csrf_token"\s+value="([^"]+)"', payload)
    assert match is not None
    return match.group(1).decode("utf-8")


def test_dev_update_route_requires_dev_role(monkeypatch, tmp_path: Path) -> None:
    app = _make_app(monkeypatch, tmp_path)
    client = app.test_client()
    _login(client, role="ADMIN")
    res = client.get("/dev/update", environ_overrides={"REMOTE_ADDR": "127.0.0.1"})
    assert res.status_code == 403


def test_dev_update_route_requires_localhost(monkeypatch, tmp_path: Path) -> None:
    app = _make_app(monkeypatch, tmp_path)
    client = app.test_client()
    _login(client, role="DEV")
    res = client.get("/dev/update", environ_overrides={"REMOTE_ADDR": "10.0.0.8"})
    assert res.status_code == 403


def test_dev_update_route_renders_for_dev_localhost(
    monkeypatch, tmp_path: Path
) -> None:
    app = _make_app(monkeypatch, tmp_path)
    client = app.test_client()
    _login(client, role="DEV")
    res = client.get("/dev/update", environ_overrides={"REMOTE_ADDR": "127.0.0.1"})
    assert res.status_code == 200
    assert b"DEV Update Center" in res.data


def test_install_action_blocked_when_disabled(monkeypatch, tmp_path: Path) -> None:
    app = _make_app(monkeypatch, tmp_path)
    client = app.test_client()
    _login(client, role="DEV")
    page = client.get("/dev/update", environ_overrides={"REMOTE_ADDR": "127.0.0.1"})
    csrf = _csrf_from_html(page.data)
    res = client.post(
        "/dev/update",
        data={"csrf_token": csrf, "action": "install"},
        environ_overrides={"REMOTE_ADDR": "127.0.0.1"},
    )
    assert res.status_code == 200
    assert b"Install-Flow ist deaktiviert" in res.data


def test_install_action_calls_update_pipeline(monkeypatch, tmp_path: Path) -> None:
    app = _make_app(monkeypatch, tmp_path)
    app.config["UPDATE_INSTALL_ENABLED"] = True
    app.config["UPDATE_INSTALL_TIMEOUT_SECONDS"] = 5
    client = app.test_client()
    _login(client, role="DEV")

    calls: list[str] = []

    def _fake_check(*args, **kwargs):
        calls.append("check")
        return {
            "checked": True,
            "update_available": True,
            "latest_version": "1.0.0-beta.2",
            "release_url": "https://example/release",
            "asset_name": "KUKANILEA.zip",
            "asset_url": "https://example/KUKANILEA.zip",
            "sha256": "a" * 64,
            "error": "",
        }

    def _fake_download(*args, **kwargs):
        calls.append("download")
        archive = tmp_path / "download.zip"
        archive.write_bytes(b"ZIP")
        return archive

    def _fake_install(*args, **kwargs):
        calls.append("install")
        return {
            "app_dir": str(tmp_path / "KUKANILEA.app"),
            "backup_dir": str(tmp_path / "KUKANILEA.app.backup"),
            "data_dir": str(tmp_path / "data"),
            "sha256": "a" * 64,
        }

    import app.web as webmod

    monkeypatch.setattr(webmod, "check_for_installable_update", _fake_check)
    monkeypatch.setattr(webmod, "download_update_asset", _fake_download)
    monkeypatch.setattr(webmod, "install_update_from_archive", _fake_install)

    page = client.get("/dev/update", environ_overrides={"REMOTE_ADDR": "127.0.0.1"})
    csrf = _csrf_from_html(page.data)
    res = client.post(
        "/dev/update",
        data={"csrf_token": csrf, "action": "install"},
        environ_overrides={"REMOTE_ADDR": "127.0.0.1"},
    )
    assert res.status_code == 200
    assert b"Update installiert" in res.data
    assert calls == ["check", "check", "download", "install"]
