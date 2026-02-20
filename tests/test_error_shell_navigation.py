from __future__ import annotations

from app import create_app


def _login(client) -> None:
    with client.session_transaction() as sess:
        sess["user"] = "dev"
        sess["role"] = "DEV"
        sess["tenant_id"] = "KUKANILEA"


def test_web_404_uses_shell_with_back_reload_controls() -> None:
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    client = app.test_client()
    _login(client)

    res = client.get("/route-does-not-exist")
    assert res.status_code == 404
    body = res.data.decode("utf-8")
    assert "KUKANILEA" in body
    assert "Zurück" in body
    assert "Neu laden" in body


def test_navigation_is_persistent_and_minimizable_in_shell() -> None:
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    client = app.test_client()
    _login(client)

    res = client.get("/settings")
    assert res.status_code == 200
    body = res.data.decode("utf-8")
    assert 'id="appNav"' in body
    assert 'id="navCollapse"' in body
    assert 'id="goBack"' in body
    assert 'id="reloadPage"' in body
    assert 'id="chatWidgetBtn"' in body
    assert "__kukaChatWidgetInit" in body
    assert "--z-nav: 4000;" in body
    assert "z-index:var(--z-nav)" in body


def test_api_404_returns_json_error_shape() -> None:
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    client = app.test_client()
    _login(client)

    res = client.get("/api/not-found")
    assert res.status_code == 404
    payload = res.get_json()
    assert isinstance(payload, dict)
    assert payload.get("ok") is False
