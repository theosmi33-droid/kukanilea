from __future__ import annotations

import json
import shutil
import uuid

from tests.time_utils import utc_now_iso


def _make_app(tmp_path, monkeypatch):
    from app import create_app
    from app.config import Config

    monkeypatch.setattr(Config, "USER_DATA_ROOT", tmp_path)
    monkeypatch.setattr(Config, "AUTH_DB", tmp_path / "auth.sqlite3")
    monkeypatch.setattr(Config, "CORE_DB", tmp_path / "core.sqlite3")
    monkeypatch.setattr(Config, "LICENSE_PATH", tmp_path / "license.json")
    monkeypatch.setattr(Config, "TRIAL_PATH", tmp_path / "trial.json")

    app = create_app()
    app.config["TESTING"] = True
    return app


def _auth_client(app):
    with app.app_context():
        auth_db = app.extensions["auth_db"]
        now = utc_now_iso()
        from app.auth import hash_password

        auth_db.upsert_tenant("KUKANILEA", "KUKANILEA", now)
        auth_db.upsert_user("admin", hash_password("admin"), now)
        auth_db.upsert_membership("admin", "KUKANILEA", "ADMIN", now)

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user"] = "admin"
        sess["role"] = "ADMIN"
        sess["tenant_id"] = "KUKANILEA"
    return client


def test_dashboard_only_lists_pending_documents_for_current_owner(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = _auth_client(app)

    from app.web import PENDING_DIR

    tenant_pending_root = PENDING_DIR / "kukanilea"
    suffix = uuid.uuid4().hex
    own_token = tenant_pending_root / f"token-owned-by-admin-{suffix}"
    foreign_token = tenant_pending_root / f"token-owned-by-alice-{suffix}"

    try:
        own_token.mkdir(parents=True, exist_ok=True)
        (own_token / "meta.json").write_text(
            json.dumps({"filename": f"admin-{suffix}.pdf", "status": "PENDING", "owner": "admin"}),
            encoding="utf-8",
        )

        foreign_token.mkdir(parents=True, exist_ok=True)
        (foreign_token / "meta.json").write_text(
            json.dumps({"filename": f"alice-{suffix}.pdf", "status": "PENDING", "owner": "alice"}),
            encoding="utf-8",
        )

        response = client.get("/dashboard")
        assert response.status_code == 200
        body = response.get_data(as_text=True)

        assert f"admin-{suffix}.pdf" in body
        assert f"alice-{suffix}.pdf" not in body
        assert own_token.name in body
        assert foreign_token.name not in body
    finally:
        shutil.rmtree(own_token, ignore_errors=True)
        shutil.rmtree(foreign_token, ignore_errors=True)
