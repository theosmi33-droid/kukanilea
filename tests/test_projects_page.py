from app import create_app


def test_projects_page_renders_for_authenticated_user():
    app = create_app()
    app.config["TESTING"] = True

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user"] = "test-user"
        sess["role"] = "ADMIN"
        sess["tenant_id"] = "KUKANILEA"

    response = client.get("/projects")

    assert response.status_code == 200
    assert b'id="project-hub"' in response.data
