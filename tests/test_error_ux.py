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


@pytest.fixture
def app():
    from app import create_app

    app = create_app()
    app.config["TESTING"] = True
    return app
