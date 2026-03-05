from __future__ import annotations

from pathlib import Path

import app as app_pkg
from app import create_app


def _seed_user_session(client, *, tenant_id: str = "KUKANILEA", tenant_db_path: str | None = None) -> None:
    with client.session_transaction() as sess:
        sess["user"] = "dev"
        sess["role"] = "DEV"
        sess["tenant_id"] = tenant_id
        if tenant_db_path:
            sess["tenant_db_path"] = tenant_db_path
        elif "tenant_db_path" in sess:
            del sess["tenant_db_path"]


def _build_app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUKANILEA_AUTH_DB", str(tmp_path / "auth.sqlite3"))
    monkeypatch.setenv("KUKANILEA_CORE_DB", str(tmp_path / "core.sqlite3"))
    return create_app()


def test_env_runtime_overrides_apply_per_app_instance(tmp_path, monkeypatch):
    auth_db = tmp_path / "auth_env.sqlite3"
    core_db = tmp_path / "core_env.sqlite3"
    license_path = tmp_path / "license_env.json"
    trial_path = tmp_path / "trial_env.json"

    monkeypatch.setenv("KUKANILEA_AUTH_DB", str(auth_db))
    monkeypatch.setenv("KUKANILEA_CORE_DB", str(core_db))
    monkeypatch.setenv("KUKANILEA_LICENSE_PATH", str(license_path))
    monkeypatch.setenv("KUKANILEA_TRIAL_PATH", str(trial_path))

    app = create_app()

    assert Path(app.config["AUTH_DB"]) == auth_db
    assert Path(app.config["CORE_DB"]) == core_db
    assert Path(app.config["LICENSE_PATH"]) == license_path
    assert Path(app.config["TRIAL_PATH"]) == trial_path


def test_runtime_wiring_updates_core_logic_db_path(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch)

    import app.core.logic as core_logic

    assert Path(core_logic.DB_PATH) == Path(app.config["CORE_DB"])
    assert Path(app_pkg.os.environ["DB_FILENAME"]) == Path(app.config["CORE_DB"])
    assert Path(app_pkg.os.environ["TOPHANDWERK_DB_FILENAME"]) == Path(app.config["CORE_DB"])


def test_before_request_binds_session_tenant_db_path_override(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    override_path = tmp_path / "tenant_override.sqlite3"

    _seed_user_session(client, tenant_db_path=str(override_path))
    response = client.get("/api/health")
    assert response.status_code == 200

    import app.core.logic as core_logic

    assert Path(core_logic.DB_PATH) == override_path
    body = response.get_json()
    assert Path(body["db_path"]) == override_path


def test_before_request_falls_back_to_core_db_without_override(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    _seed_user_session(client, tenant_db_path=None)
    response = client.get("/api/health")
    assert response.status_code == 200

    import app.core.logic as core_logic

    expected = Path(app.config["CORE_DB"])
    assert Path(core_logic.DB_PATH) == expected
    assert Path(response.get_json()["db_path"]) == expected


def test_switching_tenant_db_path_between_requests_rebinds_core_logic(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    first_path = tmp_path / "tenant_one.sqlite3"
    second_path = tmp_path / "tenant_two.sqlite3"

    _seed_user_session(client, tenant_db_path=str(first_path))
    first = client.get("/api/health")
    assert first.status_code == 200
    assert Path(first.get_json()["db_path"]) == first_path

    _seed_user_session(client, tenant_db_path=str(second_path))
    second = client.get("/api/health")
    assert second.status_code == 200
    assert Path(second.get_json()["db_path"]) == second_path

    import app.core.logic as core_logic

    assert Path(core_logic.DB_PATH) == second_path


def test_healthcheck_non_write_endpoint_stays_accessible_with_runtime_overrides(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    _seed_user_session(client, tenant_db_path=str(tmp_path / "runtime_probe.sqlite3"))

    ping = client.get("/api/ping")
    assert ping.status_code == 200
    assert ping.get_json()["ok"] is True

    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.get_json()["ok"] is True

