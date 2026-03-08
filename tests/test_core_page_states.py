from tests.time_utils import utc_now_iso


def _make_app(tmp_path, monkeypatch):
    from app import create_app
    from app.config import Config

    monkeypatch.setattr(Config, "USER_DATA_ROOT", tmp_path)
    monkeypatch.setattr(Config, "AUTH_DB", tmp_path / "auth.sqlite3")
    monkeypatch.setattr(Config, "CORE_DB", tmp_path / "core.sqlite3")
    monkeypatch.setattr(Config, "LICENSE_PATH", tmp_path / "license.json")
    monkeypatch.setattr(Config, "TRIAL_PATH", tmp_path / "trial.json")

    app = create_app()
    app.config["TESTING"] = True
    return app


def _auth_client(app):
    from app.auth import hash_password

    with app.app_context():
        auth_db = app.extensions["auth_db"]
        now = utc_now_iso()
        auth_db.upsert_tenant("KUKANILEA", "KUKANILEA", now)
        auth_db.upsert_user("admin", hash_password("admin"), now)
        auth_db.upsert_membership("admin", "KUKANILEA", "ADMIN", now)

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user"] = "admin"
        sess["role"] = "ADMIN"
        sess["tenant_id"] = "KUKANILEA"
    return client


def test_tasks_page_shows_degraded_state_on_backend_failure(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = _auth_client(app)

    from app.modules.projects import logic

    def _raise(*_args, **_kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr(logic.ProjectManager, "ensure_default_hub", _raise)

    response = client.get("/tasks")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Aufgaben werden eingeschränkt angezeigt" in body
    assert "traceback" not in body.lower()


def test_projects_page_shows_degraded_state_on_backend_failure(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = _auth_client(app)

    from app.modules.projects import logic

    def _raise(*_args, **_kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr(logic.ProjectManager, "ensure_default_hub", _raise)

    response = client.get("/projects")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Eingeschränkter Betrieb" in body
    assert 'id="project-hub"' in body
    assert "traceback" not in body.lower()
