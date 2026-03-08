from __future__ import annotations

import base64
import json
from pathlib import Path

from flask import Flask

from tests.time_utils import utc_now_iso


def _authed_client(tmp_path: Path, monkeypatch):
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

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user"] = "admin"
        sess["role"] = "ADMIN"
        sess["tenant_id"] = "KUKANILEA"
        sess["csrf_token"] = "test-csrf"

    return app, client


def _messenger_contract_app() -> Flask:
    from app.routes.messenger import bp as messenger_bp

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.secret_key = "test"

    @app.before_request
    def _auth_session():
        from flask import session

        session["user"] = "admin"
        session["role"] = "ADMIN"
        session["tenant_id"] = "KUKANILEA"
        session["csrf_token"] = "test-csrf"

    app.register_blueprint(messenger_bp)
    return app


def test_messenger_routes_present_and_confirm_contract(monkeypatch):
    app = _messenger_contract_app()
    client = app.test_client()

    import app.routes.messenger as messenger_routes

    monkeypatch.setattr(
        messenger_routes,
        "agent_answer",
        lambda _msg: {"ok": True, "text": "done", "actions": [{"type": "messenger_send"}]},
    )

    summary = client.get("/api/messenger/summary")
    chat = client.post("/api/chat", json={"msg": "schick das raus"}, headers={"X-CSRF-Token": "test-csrf"})

    assert app is not None
    assert summary.status_code == 200
    assert summary.get_json()["tool"] == "messenger"
    assert chat.status_code == 200
    body = chat.get_json()
    assert body["actions"][0]["confirm_required"] is True
    assert body["data"]["policy_events"]["confirm_required_actions"] == [{"type": "messenger_send", "reason": "confirm_gate"}]


def test_email_routes_tables_and_confirm_behavior(monkeypatch, tmp_path: Path):
    _app, client = _authed_client(tmp_path, monkeypatch)
    headers = {"X-CSRF-Token": "test-csrf"}

    assert client.get("/email").status_code == 200
    summary = client.get("/api/emailpostfach/summary")
    ingest = client.post("/api/emailpostfach/ingest", json={"provider": "imap_stub", "actor": "admin"}, headers=headers)
    draft = client.post(
        "/api/emailpostfach/draft/generate",
        json={"message": {"subject": "Anfrage", "from": "kunde@example.com"}, "actor": "admin"},
        headers=headers,
    )

    draft_id = draft.get_json()["draft"]["id"]
    blocked = client.post(
        f"/api/emailpostfach/draft/{draft_id}/send",
        json={"confirm": "no", "actor": "admin"},
        headers=headers,
    )
    sent = client.post(
        f"/api/emailpostfach/draft/{draft_id}/send",
        json={"confirm": "yes", "actor": "admin"},
        headers=headers,
    )

    assert summary.status_code == 200
    assert summary.get_json()["tool"] == "emailpostfach"
    assert ingest.status_code == 200
    assert ingest.get_json()["result"]["inserted"] == 1
    assert draft.status_code == 200
    assert blocked.status_code == 409
    assert blocked.get_json()["result"]["error"] == "explicit_confirm_required"
    assert sent.status_code == 200
    assert sent.get_json()["result"]["status"] == "sent"


def test_visualizer_routes_and_render_backend_contract(monkeypatch, tmp_path: Path):
    _app, client = _authed_client(tmp_path, monkeypatch)

    source_file = tmp_path / "sample.csv"
    source_file.write_text("name,value\nA,1\n", encoding="utf-8")
    source = base64.b64encode(str(source_file).encode("utf-8")).decode("ascii")

    import app.routes.visualizer as visualizer_routes

    monkeypatch.setattr(visualizer_routes, "_is_allowed_path", lambda _path: True)
    monkeypatch.setattr(visualizer_routes, "build_visualizer_payload", None)

    missing_backend = client.get(f"/api/visualizer/render?source={source}")
    sources = client.get("/api/visualizer/sources")

    monkeypatch.setattr(
        visualizer_routes,
        "build_visualizer_payload",
        lambda _fp, page=0, sheet="", force_ocr=False: {
            "kind": "sheet",
            "sheet": {"rows": 1, "cols": 2},
            "page": {"index": page, "count": 1},
            "force_ocr": force_ocr,
            "file": {"name": "sample.csv"},
        },
    )
    rendered = client.get(f"/api/visualizer/render?source={source}&page=1&force_ocr=1")

    assert sources.status_code == 200
    assert missing_backend.status_code == 503
    assert missing_backend.get_json()["error"] == "visualizer_logic_missing"
    assert rendered.status_code == 200
    payload = rendered.get_json()
    assert payload["kind"] == "sheet"
    assert payload["source"] == source
    assert payload["target_path"] == str(source_file)


def test_settings_read_update_rotate_parity(monkeypatch, tmp_path: Path):
    _app, client = _authed_client(tmp_path, monkeypatch)
    headers = {"X-CSRF-Token": "test-csrf"}

    settings_page = client.get("/admin/settings")
    assert settings_page.status_code == 200

    missing_confirm = client.post(
        "/admin/settings/system",
        data={"language": "en", "timezone": "UTC", "backup_interval": "weekly", "log_level": "debug"},
        headers=headers,
    )
    assert missing_confirm.status_code == 400
    assert missing_confirm.get_json()["error"] == "confirm_required"

    updated = client.post(
        "/admin/settings/system",
        data={
            "language": "en",
            "timezone": "UTC",
            "backup_interval": "weekly",
            "log_level": "debug",
            "memory_retention_days": "45",
            "briefing_rss_feeds": "https://example.com/feed\n",
            "briefing_cron": "0 6 * * *",
            "external_apis_enabled": "on",
            "confirm": "CONFIRM",
        },
        headers=headers,
    )
    assert updated.status_code in {302, 303}

    settings_json = json.loads((tmp_path / "system_settings.json").read_text(encoding="utf-8"))
    assert settings_json["language"] == "en"
    assert settings_json["timezone"] == "UTC"
    assert settings_json["log_level"] == "DEBUG"
    assert settings_json["memory_retention_days"] == 45
    assert settings_json["briefing_rss_feeds"] == ["https://example.com/feed"]

    import app.routes.admin_tenants as admin_routes

    priv = tmp_path / "mesh_priv.key"
    pub = tmp_path / "mesh_pub.key"
    priv.write_text("old", encoding="utf-8")
    pub.write_text("old", encoding="utf-8")

    calls: list[str] = []

    def _fake_ensure_mesh_identity():
        calls.append("called")
        priv.write_text("new", encoding="utf-8")
        pub.write_text("new", encoding="utf-8")
        return "pub", "node"

    monkeypatch.setattr(admin_routes, "get_identity_paths", lambda: (priv, pub))
    monkeypatch.setattr(admin_routes, "ensure_mesh_identity", _fake_ensure_mesh_identity)

    rotate_missing_confirm = client.post("/admin/settings/mesh/rotate-key", data={}, headers=headers)
    assert rotate_missing_confirm.status_code == 400

    rotate = client.post(
        "/admin/settings/mesh/rotate-key",
        data={"confirm": "YES"},
        headers=headers,
    )
    assert rotate.status_code in {302, 303}
    assert calls == ["called"]
    assert priv.read_text(encoding="utf-8") == "new"
    assert pub.read_text(encoding="utf-8") == "new"
