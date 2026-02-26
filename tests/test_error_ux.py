import pytest

from app.errors import error_envelope


def test_error_envelope_structure(app):
    with app.app_context():
        code = "TEST_ERROR"
        message = "Test message"
        details = {"field": "missing"}

        payload = error_envelope(code, message, details=details)

        assert payload["ok"] is False
        assert payload["error"]["code"] == code
        assert payload["error"]["message"] == message
        assert payload["error"]["details"]["field"] == "missing"


def test_error_envelope_request_id(app):
    with app.app_context():
        from flask import g

        g.request_id = "REQ-123"

        payload = error_envelope("CODE", "Msg")
        assert payload["error"]["details"]["request_id"] == "REQ-123"


def test_html_error_response(app):
    client = app.test_client()
    # Mock login to avoid redirect
    with client.session_transaction() as sess:
        sess["user"] = "test-user"
        sess["role"] = "ADMIN"

    # Propose a 404
    response = client.get("/this-page-definitely-does-not-exist")
    assert response.status_code == 404
    assert b"404 - Nicht gefunden" in response.data
    assert "text/html" in response.content_type


def test_api_json_error_response(app):
    client = app.test_client()
    # Mock login to avoid unauthorized
    with client.session_transaction() as sess:
        sess["user"] = "test-user"
        sess["role"] = "ADMIN"

    # Propose a 404 but with JSON header
    response = client.get(
        "/api/invalid-endpoint", headers={"Accept": "application/json"}
    )
    assert response.status_code == 404
    assert response.is_json
    assert response.get_json()["error"]["code"] == "NOT_FOUND"


@pytest.fixture
def app():
    from app import create_app

    app = create_app()
    app.config["TESTING"] = True
    return app
