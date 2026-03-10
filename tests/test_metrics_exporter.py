from __future__ import annotations

from pathlib import Path

import pytest

from tests.time_utils import utc_now_iso


@pytest.fixture()
def app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
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
        auth_db.upsert_user("admin", hash_password("admin"), now)
        auth_db.upsert_membership("admin", "KUKANILEA", "ADMIN", now)
        auth_db.upsert_user("readonly", hash_password("readonly"), now)
        auth_db.upsert_membership("readonly", "KUKANILEA", "READONLY", now)

    return app


@pytest.fixture()
def client(app):
    return app.test_client()


def test_metrics_requires_login(client):
    response = client.get("/metrics")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_metrics_requires_admin_role(client):
    with client.session_transaction() as sess:
        sess["user"] = "readonly"
        sess["role"] = "READONLY"
        sess["tenant_id"] = "KUKANILEA"

    response = client.get("/metrics")

    assert response.status_code == 403


def test_metrics_allows_admin(client):
    with client.session_transaction() as sess:
        sess["user"] = "admin"
        sess["role"] = "ADMIN"
        sess["tenant_id"] = "KUKANILEA"

    response = client.get("/metrics")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "kukanilea_last_backup_age_seconds" in body
    assert "kukanilea_outbound_queue_pending" in body
