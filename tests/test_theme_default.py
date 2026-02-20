from __future__ import annotations

from app import create_app


def _login(client, role: str = "DEV") -> None:
    with client.session_transaction() as sess:
        sess["user"] = "dev"
        sess["role"] = role
        sess["tenant_id"] = "KUKANILEA"


def test_shell_default_theme_is_light() -> None:
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    client = app.test_client()
    _login(client)
    res = client.get("/")
    assert res.status_code == 200
    body = res.get_data(as_text=True)
    assert 'data-theme="light"' in body
