from __future__ import annotations

from app import create_app, web


def _login(client, role: str):
    with client.session_transaction() as sess:
        sess["user"] = "dev"
        sess["role"] = role
        sess["tenant_id"] = "KUKANILEA"


def test_settings_available_for_operator():
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    client = app.test_client()
    _login(client, "OPERATOR")
    res = client.get("/settings")
    assert res.status_code == 200
    assert b"Inaktivitaets-Timeout" in res.data


def test_open_by_token_creates_pending(tmp_path, monkeypatch):
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    client = app.test_client()
    _login(client, "ADMIN")

    sample = tmp_path / "doc.pdf"
    sample.write_text("sample")
    monkeypatch.setattr(
        web, "db_latest_path_for_doc", lambda doc_id, tenant_id="": str(sample)
    )
    monkeypatch.setattr(web, "analyze_to_pending", lambda path: "newtoken123")

    res = client.post("/api/open", json={"token": "abc123"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["ok"] is True
    assert data["token"] == "newtoken123"
