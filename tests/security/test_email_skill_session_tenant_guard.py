from __future__ import annotations

from pathlib import Path

import pytest

from tests.time_utils import utc_now_iso


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from app import create_app
    from app.auth import hash_password
    from app.config import Config

    monkeypatch.setattr(Config, "USER_DATA_ROOT", tmp_path)
    monkeypatch.setattr(Config, "AUTH_DB", tmp_path / "auth.sqlite3")
    monkeypatch.setattr(Config, "CORE_DB", tmp_path / "core.sqlite3")
    monkeypatch.setattr(Config, "LICENSE_PATH", tmp_path / "license.json")
    monkeypatch.setattr(Config, "TRIAL_PATH", tmp_path / "trial.json")

    app = create_app()
    app.config["TESTING"] = True

    with app.app_context():
        auth_db = app.extensions["auth_db"]
        now = utc_now_iso()
        auth_db.upsert_tenant("KUKANILEA", "KUKANILEA", now)
        auth_db.upsert_user("dev", hash_password("dev"), now)
        auth_db.upsert_membership("dev", "KUKANILEA", "DEV", now)

    c = app.test_client()
    with c.session_transaction() as sess:
        sess["user"] = "dev"
        sess["role"] = "DEV"
        sess["tenant_id"] = "KUKANILEA"
        sess["csrf_token"] = "csrf-test"
    return c


def test_ai_execute_rejects_missing_session_tenant(client, monkeypatch: pytest.MonkeyPatch):
    import app.web as web_module

    monkeypatch.setattr(web_module, "current_tenant", lambda: "")

    response = client.post(
        "/api/ai/execute",
        json={"skill": "email.search", "payload": {"query": "angebot"}, "confirm": False},
        headers={"X-CSRF-Token": "csrf-test"},
    )

    assert response.status_code == 403
    assert response.get_json()["error"] == "tenant_required"
