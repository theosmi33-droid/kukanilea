from __future__ import annotations

from app import create_app


def test_manifest_endpoint() -> None:
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    client = app.test_client()
    res = client.get("/app.webmanifest")
    assert res.status_code == 200
    payload = res.get_json() or {}
    assert payload.get("name")
    assert payload.get("start_url")
    assert payload.get("display") == "standalone"
    assert payload.get("icons")
    icons = payload.get("icons") or []
    assert any(
        (icon or {}).get("src") == "/static/icons/app-icon.png" for icon in icons
    )


def test_service_worker_endpoint() -> None:
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    client = app.test_client()
    res = client.get("/sw.js")
    assert res.status_code == 200
    text = res.get_data(as_text=True)
    assert "CACHE='kukanilea-crm-v1'" in text
    assert "/static/icons/app-icon.png" in text
