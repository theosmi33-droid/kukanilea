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
        with auth_db._db() as con:
            con.execute(
                """
                INSERT INTO api_outbound_queue(
                    id, tenant_id, target_system, payload, status, created_at, error_message, last_attempt
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "evt-1",
                    "KUKANILEA",
                    "lexoffice",
                    "{}",
                    "failed",
                    now,
                    "token expired",
                    now,
                ),
            )

    return app


@pytest.fixture()
def client(app):
    return app.test_client()


def _login(client, *, user: str, role: str) -> None:
    with client.session_transaction() as sess:
        sess["user"] = user
        sess["role"] = role
        sess["tenant_id"] = "KUKANILEA"


def test_outbound_status_redacts_failure_metadata_for_readonly_role(client):
    _login(client, user="readonly", role="READONLY")

    response = client.get("/api/outbound/status")

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["stats"]["failed"] == 1
    assert body["recent_failed"] == []
    assert body["recent_failed_redacted"] is True


def test_outbound_status_includes_failure_metadata_for_admin_role(client):
    _login(client, user="admin", role="ADMIN")

    response = client.get("/api/outbound/status")

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert len(body["recent_failed"]) == 1
    assert body["recent_failed"][0]["error_message"] == "token expired"
    assert body["recent_failed_redacted"] is False
