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


def test_mail_triage_handles_non_object_json(client):
    response = client.post(
        "/api/mail/triage",
        json=["not", "an", "object"],
        headers={"X-CSRF-Token": "csrf-test"},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert "triage" in body


def test_mail_draft_generate_handles_non_object_json(client):
    response = client.post(
        "/api/mail/draft/generate",
        json=["not", "an", "object"],
        headers={"X-CSRF-Token": "csrf-test"},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert "draft" in body


def test_mail_summary_invalid_sla_hours_uses_default(client):
    response = client.get("/api/mail/summary?sla_hours=not-a-number")

    assert response.status_code == 200
    body = response.get_json()
    assert body["metrics"]["sla_threshold_hours"] == 24


def test_mail_health_invalid_sla_hours_uses_default(client):
    response = client.get("/api/mail/health?sla_hours=not-a-number")

    assert response.status_code == 200
    body = response.get_json()
    assert body["metrics"]["sla_threshold_hours"] == 24
