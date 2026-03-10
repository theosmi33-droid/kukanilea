from app import create_app


def test_multi_progress_requires_auth_for_non_local_requests():
    app = create_app()
    app.config["TESTING"] = True

    client = app.test_client()
    response = client.get(
        "/api/progress?tokens=test-token",
        environ_overrides={"REMOTE_ADDR": "198.51.100.7"},
    )

    assert response.status_code == 401
    assert response.is_json
    payload = response.get_json()
    assert "error" in payload
