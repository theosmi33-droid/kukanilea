from __future__ import annotations

import sqlite3
import threading
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

    import app.core.logic as core_logic

    bind_calls: list[Path | None] = []
    original_bind = core_logic.bind_request_db_path

    def _record_bind(path: Path | None) -> None:
        bind_calls.append(Path(path) if path else None)
        original_bind(path)

    monkeypatch.setattr(core_logic, "bind_request_db_path", _record_bind)
    _seed_user_session(client, tenant_db_path=str(override_path))
    response = client.get("/api/health")
    assert response.status_code == 200

    assert Path(core_logic.DB_PATH) == Path(app.config["CORE_DB"])
    assert Path(core_logic._active_db_path()) == Path(app.config["CORE_DB"])
    assert override_path in bind_calls
    assert bind_calls[-1] is None


def test_aufgaben_api_respects_session_tenant_db_path(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    tenant_db = tmp_path / "tenant_tasks.sqlite3"

    _seed_user_session(client, tenant_db_path=str(tenant_db))
    created = client.post("/api/aufgaben", json={"title": "Tenant Scoped Task"})
    assert created.status_code == 201

    with sqlite3.connect(tenant_db) as con:
        row = con.execute(
            "SELECT tenant, title FROM aufgaben_tasks WHERE title=?",
            ("Tenant Scoped Task",),
        ).fetchone()
    assert row is not None
    assert row[0] == "KUKANILEA"
    assert row[1] == "Tenant Scoped Task"

    with sqlite3.connect(str(app.config["CORE_DB"])) as con:
        try:
            default_count = con.execute(
                "SELECT COUNT(*) FROM aufgaben_tasks WHERE title=?",
                ("Tenant Scoped Task",),
            ).fetchone()[0]
        except sqlite3.OperationalError:
            default_count = 0
    assert default_count == 0


def test_before_request_falls_back_to_core_db_without_override(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    _seed_user_session(client, tenant_db_path=None)
    response = client.get("/api/health")
    assert response.status_code == 200

    import app.core.logic as core_logic

    expected = Path(app.config["CORE_DB"])
    assert Path(core_logic.DB_PATH) == expected
    assert Path(core_logic._active_db_path()) == expected


def test_switching_tenant_db_path_between_requests_rebinds_core_logic(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    first_path = tmp_path / "tenant_one.sqlite3"
    second_path = tmp_path / "tenant_two.sqlite3"
    import app.core.logic as core_logic

    bind_calls: list[Path | None] = []
    original_bind = core_logic.bind_request_db_path

    def _record_bind(path: Path | None) -> None:
        bind_calls.append(Path(path) if path else None)
        original_bind(path)

    monkeypatch.setattr(core_logic, "bind_request_db_path", _record_bind)

    _seed_user_session(client, tenant_db_path=str(first_path))
    first = client.get("/api/health")
    assert first.status_code == 200

    assert Path(core_logic.DB_PATH) == Path(app.config["CORE_DB"])
    assert Path(core_logic._active_db_path()) == Path(app.config["CORE_DB"])

    _seed_user_session(client, tenant_db_path=str(second_path))
    second = client.get("/api/health")
    assert second.status_code == 200

    assert Path(core_logic.DB_PATH) == Path(app.config["CORE_DB"])
    assert Path(core_logic._active_db_path()) == Path(app.config["CORE_DB"])
    non_none = [item for item in bind_calls if item is not None]
    assert first_path in non_none
    assert second_path in non_none
    assert bind_calls[-1] is None


def test_bind_request_db_path_none_restores_global_fallback(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch)
    import app.core.logic as core_logic

    global_path = Path(app.config["CORE_DB"])
    custom_path = tmp_path / "isolated.sqlite3"

    core_logic.bind_request_db_path(custom_path)
    assert Path(core_logic._active_db_path()) == custom_path

    core_logic.bind_request_db_path(None)
    assert Path(core_logic._active_db_path()) == global_path


def test_db_initialization_is_tracked_per_active_path(tmp_path, monkeypatch):
    _build_app(tmp_path, monkeypatch)
    import app.core.logic as core_logic

    first_path = tmp_path / "tenant_a.sqlite3"
    second_path = tmp_path / "tenant_b.sqlite3"

    core_logic.bind_request_db_path(first_path)
    con = core_logic._db()
    con.close()
    assert first_path.exists()

    core_logic.bind_request_db_path(second_path)
    con = core_logic._db()
    con.close()
    assert second_path.exists()

    initialized = set(core_logic._DB_INITIALIZED_PATHS)
    assert str(first_path.resolve()) in initialized
    assert str(second_path.resolve()) in initialized

    core_logic.bind_request_db_path(None)


def test_before_request_error_clears_request_binding(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    import app.core.logic as core_logic
    import app.web as web_module

    prebound = tmp_path / "prebound.sqlite3"
    core_logic.bind_request_db_path(prebound)
    assert Path(core_logic._active_db_path()) == prebound

    def _raise_path_error():
        raise RuntimeError("tenant_path_lookup_failed")

    monkeypatch.setattr(web_module, "_get_tenant_db_path", _raise_path_error)
    _seed_user_session(client, tenant_db_path=str(tmp_path / "ignored.sqlite3"))
    response = client.get("/api/health")
    assert response.status_code == 200

    assert Path(core_logic._active_db_path()) == Path(core_logic.DB_PATH)


def test_request_db_binding_is_thread_local(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch)
    import app.core.logic as core_logic

    default_path = Path(app.config["CORE_DB"])
    first_path = tmp_path / "thread_one.sqlite3"
    second_path = tmp_path / "thread_two.sqlite3"
    seen: dict[str, Path] = {}
    lock = threading.Lock()

    def _worker(name: str, db_path: Path) -> None:
        core_logic.bind_request_db_path(db_path)
        con = core_logic._db()
        con.close()
        with lock:
            seen[name] = Path(core_logic._active_db_path())
        core_logic.bind_request_db_path(None)

    t1 = threading.Thread(target=_worker, args=("one", first_path))
    t2 = threading.Thread(target=_worker, args=("two", second_path))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert seen["one"] == first_path
    assert seen["two"] == second_path
    assert Path(core_logic.DB_PATH) == default_path
    assert Path(core_logic._active_db_path()) == default_path


def test_rebinding_same_path_keeps_single_init_marker(tmp_path, monkeypatch):
    _build_app(tmp_path, monkeypatch)
    import app.core.logic as core_logic

    tenant_path = tmp_path / "tenant_rebind.sqlite3"

    core_logic.bind_request_db_path(tenant_path)
    con = core_logic._db()
    con.close()

    initialized_before = set(core_logic._DB_INITIALIZED_PATHS)
    con = core_logic._db()
    con.close()
    initialized_after = set(core_logic._DB_INITIALIZED_PATHS)

    assert initialized_before == initialized_after
    assert str(tenant_path.resolve()) in initialized_after
    core_logic.bind_request_db_path(None)


def test_health_does_not_reinitialize_db_for_same_path(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    _seed_user_session(client, tenant_db_path=None)

    import app.core.logic as core_logic

    db_key = str(Path(app.config["CORE_DB"]).resolve())
    original_db_init = core_logic.db_init
    init_calls = {"count": 0}

    def _counting_db_init() -> None:
        init_calls["count"] += 1
        original_db_init()

    monkeypatch.setattr(core_logic, "db_init", _counting_db_init)
    core_logic._DB_INITIALIZED_PATHS.discard(db_key)

    first = client.get("/api/health")
    second = client.get("/api/health")

    assert first.status_code == 200
    assert second.status_code == 200
    assert init_calls["count"] == 1


def test_set_db_path_does_not_override_active_request_binding(tmp_path, monkeypatch):
    _build_app(tmp_path, monkeypatch)
    import app.core.logic as core_logic

    original_global = Path(core_logic.DB_PATH)
    request_path = tmp_path / "request_bound.sqlite3"
    new_global = tmp_path / "new_global.sqlite3"
    try:
        core_logic.bind_request_db_path(request_path)
        assert Path(core_logic._active_db_path()) == request_path

        core_logic.set_db_path(new_global)
        assert Path(core_logic.DB_PATH) == new_global
        assert Path(core_logic._active_db_path()) == request_path

        core_logic.bind_request_db_path(None)
        assert Path(core_logic._active_db_path()) == new_global
    finally:
        core_logic.bind_request_db_path(None)
        core_logic.set_db_path(original_global)


def test_before_request_can_recover_after_lookup_error(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    import app.core.logic as core_logic
    import app.web as web_module

    base_path = Path(app.config["CORE_DB"])
    failing_path = tmp_path / "will_not_apply.sqlite3"
    healthy_path = tmp_path / "healthy.sqlite3"
    bind_calls: list[Path | None] = []
    original_bind = core_logic.bind_request_db_path

    def _record_bind(path: Path | None) -> None:
        bind_calls.append(Path(path) if path else None)
        original_bind(path)

    monkeypatch.setattr(core_logic, "bind_request_db_path", _record_bind)

    _seed_user_session(client, tenant_db_path=str(failing_path))
    monkeypatch.setattr(web_module, "_get_tenant_db_path", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    failed = client.get("/api/health")
    assert failed.status_code == 200
    assert Path(core_logic._active_db_path()) == base_path

    monkeypatch.setattr(web_module, "_get_tenant_db_path", lambda: healthy_path)
    healthy = client.get("/api/health")
    assert healthy.status_code == 200
    assert Path(core_logic._active_db_path()) == base_path
    assert healthy_path in [item for item in bind_calls if item is not None]


def test_healthcheck_requires_authentication_for_anonymous_requests(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    response = client.get("/api/health")
    assert response.status_code == 401
    body = response.get_json()
    assert body["error"]["code"] == "auth_required"


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
