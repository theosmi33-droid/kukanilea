from __future__ import annotations

from app import create_app


def _login(client, role: str = "DEV", username: str = "dev") -> None:
    with client.session_transaction() as sess:
        sess["user"] = username
        sess["role"] = role
        sess["tenant_id"] = "KUKANILEA"


def test_default_theme_is_light_when_no_preference() -> None:
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    client = app.test_client()
    _login(client, username="theme_default_user")

    res = client.get("/")
    assert res.status_code == 200
    assert 'data-theme="light"' in res.get_data(as_text=True)


def test_theme_preference_loaded_from_auth_db() -> None:
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    auth_db = app.extensions["auth_db"]
    auth_db.set_user_preference("theme_dark_user", "ui.theme", "dark")
    client = app.test_client()
    _login(client, username="theme_dark_user")

    res = client.get("/")
    assert res.status_code == 200
    assert 'data-theme="dark"' in res.get_data(as_text=True)


def test_theme_preference_route_persists_setting() -> None:
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    client = app.test_client()
    _login(client, username="theme_route_user")

    res = client.post("/settings/ui/theme", json={"theme": "dark"})
    assert res.status_code == 200
    assert res.get_json()["ok"] is True

    auth_db = app.extensions["auth_db"]
    prefs = auth_db.get_user_preferences("theme_route_user", keys=["ui.theme"])
    assert prefs.get("ui.theme") == "dark"


def test_sidebar_preference_route_and_shell_default() -> None:
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    client = app.test_client()
    _login(client, username="sidebar_route_user")

    save = client.post("/settings/ui/sidebar", json={"collapsed": True})
    assert save.status_code == 200
    assert save.get_json()["collapsed"] is True

    res = client.get("/")
    assert res.status_code == 200
    body = res.get_data(as_text=True)
    assert "const serverNavCollapsed = true;" in body


def test_theme_route_rejects_invalid_value() -> None:
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    client = app.test_client()
    _login(client, username="theme_invalid_user")

    res = client.post("/settings/ui/theme", json={"theme": "sepia"})
    assert res.status_code == 400
    payload = res.get_json()
    assert payload["ok"] is False
    assert payload["error_code"] == "validation_error"
