from __future__ import annotations

from app import create_app


def test_csp_header_present_on_login() -> None:
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    client = app.test_client()

    response = client.get("/login")
    assert response.status_code in (200, 302, 303)
    csp = str(response.headers.get("Content-Security-Policy") or "")
    assert "default-src 'self'" in csp
    assert "font-src 'self'" in csp
    assert "script-src 'self' 'unsafe-inline'" in csp
