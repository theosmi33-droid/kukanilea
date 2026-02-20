from __future__ import annotations

from app import create_app


def _login(client, role: str = "OPERATOR") -> None:
    with client.session_transaction() as sess:
        sess["user"] = "dev"
        sess["role"] = role
        sess["tenant_id"] = "KUKANILEA"


def test_non_api_error_renders_shell_for_html_navigation() -> None:
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    client = app.test_client()
    _login(client, role="OPERATOR")

    res = client.get("/license", headers={"Accept": "text/html"})
    assert res.status_code == 403
    body = res.get_data(as_text=True)
    assert 'data-app-shell="1"' in body
    assert "Request-ID:" in body
    assert "Neu laden" in body
    assert "Zurueck" in body


def test_non_api_error_can_still_return_json() -> None:
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    client = app.test_client()
    _login(client, role="OPERATOR")

    res = client.get("/license", headers={"Accept": "application/json"})
    assert res.status_code == 403
    payload = res.get_json() or {}
    assert payload.get("error", {}).get("code") == "forbidden"


def test_non_api_error_defaults_to_html_when_accept_unspecified() -> None:
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    client = app.test_client()
    _login(client, role="OPERATOR")

    res = client.get("/license")
    assert res.status_code == 403
    body = res.get_data(as_text=True)
    assert 'data-app-shell="1"' in body
    assert "Request-ID:" in body


def test_global_http_exception_honors_accept_json() -> None:
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    client = app.test_client()
    _login(client, role="OPERATOR")

    res = client.get("/route-does-not-exist", headers={"Accept": "application/json"})
    assert res.status_code == 404
    payload = res.get_json() or {}
    assert payload.get("error", {}).get("code") == "http_error"
